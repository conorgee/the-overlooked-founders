import logging
import math
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import LLM_MODEL, MAX_TOKENS_CHAT, MAX_TOKENS_REWRITE
from deps import supabase, groq_client, authenticate
from lib.knowledge_retrieval import retrieve_for_chat, format_chunks_for_prompt
from helpers.utils import extract_sources

logger = logging.getLogger(__name__)
router = APIRouter()

CONTEXT_PRONOUNS = re.compile(
    r"\b(that|this|it|those|these|them|there|more|also|too|elaborate|explain)\b",
    re.IGNORECASE,
)


def _wilson_lower_bound(positive: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    p = positive / total
    return (p + z * z / (2 * total) - z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)) / (1 + z * z / total)


class ChatBody(BaseModel):
    message: str
    history: list[dict] | None = None
    user_id: str | None = None


async def _rewrite_query(message: str, history: list[dict]) -> str | None:
    recent = (history or [])[-4:]
    context_str = "\n".join(
        f"{m['role']}: {m['content'][:200]}" for m in recent
    )

    completion = groq_client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=MAX_TOKENS_REWRITE,
        messages=[
            {
                "role": "system",
                "content": "Rewrite the user's latest message as a standalone search query that captures the full intent based on conversation context. Reply with ONLY the rewritten query, nothing else.",
            },
            {
                "role": "user",
                "content": f'Conversation:\n{context_str}\n\nLatest message: "{message}"\n\nStandalone query:',
            },
        ],
    )

    return (completion.choices[0].message.content or "").strip() or None


async def _build_retrieval_query(message: str, history: list[dict] | None) -> str:
    words = message.strip().split()
    has_history = bool(history)

    if not has_history or (len(words) >= 7 and not CONTEXT_PRONOUNS.search(message)):
        return message

    if len(words) < 7 and CONTEXT_PRONOUNS.search(message):
        try:
            rewritten = await _rewrite_query(message, history)
            if rewritten:
                logger.info("Rewrote '%s' -> '%s'", message, rewritten)
                return rewritten
        except Exception as err:
            logger.info("Query rewrite failed, using history enrichment: %s", err)

    recent = (history or [])[-4:]
    context = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in recent)
    return f"{context}\n{message}"


@router.post("/chat", dependencies=[Depends(authenticate)])
async def chat(body: ChatBody):
    if not body.message:
        raise HTTPException(status_code=400, detail="message is required")

    try:
        retrieval_query = await _build_retrieval_query(body.message, body.history)
        chunks = retrieve_for_chat(supabase, retrieval_query)
        knowledge_text = format_chunks_for_prompt(chunks)

        system_prompt = f"""You are a mentor representing the collective wisdom of CEOs of successful businesses, with decades of experience building and scaling companies.

You are mentoring a cohort of 25 young entrepreneurs through an 8-week AI-powered programme run by The Overlooked Founders. You give advice that is grounded in real experience and knowledge — not generic business advice.

IMPORTANT RULES:
1. Only answer based on the knowledge base provided below. If the question is outside your knowledge, say so honestly.
2. Always cite the specific source(s) your answer draws from using this format at the end of your response:
   📎 Source: [exact source name from the knowledge base]
3. Be conversational, warm, and direct — like a real mentor, not a textbook.
4. Share specific examples from your experience when relevant.
5. Keep responses concise but actionable — these are busy founders.

=== YOUR KNOWLEDGE BASE ===
{knowledge_text}
=== END KNOWLEDGE BASE ==="""

        messages = [
            {"role": "system", "content": system_prompt},
            *((body.history or [])[-10:]),
            {"role": "user", "content": body.message},
        ]

        completion = groq_client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=MAX_TOKENS_CHAT,
            messages=messages,
        )

        reply = completion.choices[0].message.content or ""
        sources = extract_sources(reply)

        # Persist assistant message server-side and log retrieval provenance
        message_id = None
        if body.user_id:
            try:
                insert_res = supabase.table("chat_messages").insert({
                    "user_id": body.user_id,
                    "role": "assistant",
                    "content": reply,
                    "sources_cited": sources if sources else None,
                }).execute()
                if insert_res.data:
                    message_id = insert_res.data[0]["id"]

                    # Log which chunks were retrieved for this response
                    logs = [
                        {
                            "message_id": message_id,
                            "chunk_id": c.get("id"),
                            "rank": rank,
                            "rrf_score": c.get("rrf_score"),
                            "similarity": c.get("similarity"),
                        }
                        for rank, c in enumerate(chunks)
                        if c.get("id")
                    ]
                    if logs:
                        supabase.table("retrieval_logs").insert(logs).execute()
            except Exception as persist_err:
                logger.warning("Failed to persist message/retrieval logs: %s", persist_err)

        return {"reply": reply, "sources": sources, "message_id": message_id}
    except Exception as err:
        logger.error("Chat error: %s", err)
        raise HTTPException(status_code=500, detail=str(err))


class FeedbackBody(BaseModel):
    message_id: str
    feedback: str


@router.post("/chat/feedback", dependencies=[Depends(authenticate)])
async def submit_feedback(body: FeedbackBody):
    if body.feedback not in ("helpful", "not_helpful"):
        raise HTTPException(400, "feedback must be 'helpful' or 'not_helpful'")

    # Update chat_messages feedback column
    supabase.table("chat_messages").update({
        "feedback": body.feedback,
        "feedback_at": "now()",
    }).eq("id", body.message_id).execute()

    # Update chunk_quality for all chunks retrieved in this response
    logs_res = supabase.table("retrieval_logs").select("chunk_id").eq(
        "message_id", body.message_id
    ).execute()

    for log in (logs_res.data or []):
        chunk_id = log["chunk_id"]
        if not chunk_id:
            continue

        existing = supabase.table("chunk_quality").select("*").eq(
            "chunk_id", chunk_id
        ).execute()

        if existing.data:
            row = existing.data[0]
            helpful = row["helpful_count"] + (1 if body.feedback == "helpful" else 0)
            not_helpful = row["not_helpful_count"] + (1 if body.feedback == "not_helpful" else 0)
            wilson = _wilson_lower_bound(helpful, helpful + not_helpful)
            supabase.table("chunk_quality").update({
                "helpful_count": helpful,
                "not_helpful_count": not_helpful,
                "wilson_score": wilson,
            }).eq("chunk_id", chunk_id).execute()
        else:
            helpful = 1 if body.feedback == "helpful" else 0
            not_helpful = 1 if body.feedback == "not_helpful" else 0
            wilson = _wilson_lower_bound(helpful, helpful + not_helpful)
            supabase.table("chunk_quality").insert({
                "chunk_id": chunk_id,
                "helpful_count": helpful,
                "not_helpful_count": not_helpful,
                "wilson_score": wilson,
            }).execute()

    return {"ok": True}
