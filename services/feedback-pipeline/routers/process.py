import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import LLM_MODEL, MAX_TOKENS_CHAT
from deps import supabase, groq_client, authenticate
from lib.knowledge_retrieval import retrieve_for_week, format_chunks_for_prompt
from helpers.transcription import transcribe_video
from helpers.utils import extract_sources

logger = logging.getLogger(__name__)
router = APIRouter()

WEEK_TITLES = {
    1: "Idea Validation",
    2: "Customer Discovery",
    3: "Business Model",
    4: "MVP Strategy",
    5: "Go-To-Market",
    6: "Growth & Metrics",
    7: "Team & Operations",
    8: "Pitch & Next Steps",
}


def _build_feedback_prompt(week_number: int, knowledge_text: str) -> str:
    week_title = WEEK_TITLES.get(week_number, f"Week {week_number}")

    return f"""You are a mentor for The Overlooked Founders, an 8-week AI-powered programme for young entrepreneurs from underrepresented backgrounds. You are reviewing a participant's Week {week_number} video submission on the topic of "{week_title}".

Your task is to provide personalized, actionable feedback on their video update. Be warm, encouraging, but honest. Structure your response as:

1. **Summary**: Briefly summarize what the participant shared (2-3 sentences)
2. **Strengths**: What they're doing well (2-3 points)
3. **Areas to Explore**: Specific suggestions grounded in your knowledge base (2-3 points)
4. **Action Items**: 2-3 concrete next steps for the coming week

RULES:
- Ground your advice in the knowledge base below. Cite sources using: 📎 Source: [exact source name]
- Be conversational and direct, like a real mentor.
- Reference specific things they said in their video to show you listened.
- Keep total response under 500 words.

=== YOUR KNOWLEDGE BASE ===
{knowledge_text}
=== END KNOWLEDGE BASE ==="""


class ProcessBody(BaseModel):
    submissionId: str


@router.post("/process", dependencies=[Depends(authenticate)])
async def process_submission(body: ProcessBody):
    logger.info("Starting pipeline for submission %s", body.submissionId)

    sub_res = (
        supabase.table("weekly_submissions")
        .select("id, video_url, week_number, status, user_id")
        .eq("id", body.submissionId)
        .single()
        .execute()
    )

    submission = sub_res.data
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission["status"] != "submitted":
        logger.info("Skipping — status is already '%s'", submission["status"])
        return {"message": f"Already {submission['status']}"}

    if not submission.get("video_url"):
        raise HTTPException(status_code=400, detail="No video URL on submission")

    supabase.table("weekly_submissions").update({"status": "processing"}).eq("id", body.submissionId).execute()

    try:
        logger.info("Transcribing video...")
        transcript = transcribe_video(groq_client, submission["video_url"])
        logger.info("Transcript: %s...", transcript[:100])

        supabase.table("weekly_submissions").update({"transcript": transcript}).eq("id", body.submissionId).execute()

        logger.info("Retrieving knowledge...")
        chunks = retrieve_for_week(supabase, submission["week_number"])
        knowledge_text = format_chunks_for_prompt(chunks)
        logger.info("Retrieved %d knowledge chunks", len(chunks))

        logger.info("Generating feedback...")
        system_prompt = _build_feedback_prompt(submission["week_number"], knowledge_text)

        completion = groq_client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=MAX_TOKENS_CHAT,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Here is the transcript of the participant's Week {submission['week_number']} video submission:\n\n---\n{transcript}\n---\n\nPlease provide your mentorship feedback.",
                },
            ],
        )

        feedback_text = completion.choices[0].message.content or ""
        sources = extract_sources(feedback_text)

        logger.info("Feedback generated (%d chars, %d sources)", len(feedback_text), len(sources))

        supabase.table("ai_responses").insert({
            "submission_id": body.submissionId,
            "response_text": feedback_text,
            "sources_cited": sources if sources else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        supabase.table("weekly_submissions").update({"status": "responded"}).eq("id", body.submissionId).execute()

        logger.info("Pipeline complete for submission %s", body.submissionId)
        return {
            "success": True,
            "transcript_length": len(transcript),
            "feedback_length": len(feedback_text),
        }
    except Exception as err:
        logger.error("Pipeline error: %s", err)
        supabase.table("weekly_submissions").update({"status": "submitted"}).eq("id", body.submissionId).execute()
        raise HTTPException(status_code=500, detail=str(err))
