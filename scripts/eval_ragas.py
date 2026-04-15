"""
RAGAS Evaluation Framework
Evaluates the full RAG pipeline with four quality metrics:
  - Context Precision: are retrieved chunks relevant to the question?
  - Context Recall: do retrieved chunks cover the ground truth answer?
  - Faithfulness: does the generated answer stick to retrieved context?
  - Answer Relevance: does the answer actually address the question?

Uses Groq LLM as judge. Requires backend running on localhost:3001.
Run: python scripts/eval_ragas.py
"""

import json
import os
import re
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"

import httpx
import mlflow

root = Path(__file__).resolve().parent.parent

mlflow.set_tracking_uri(f"sqlite:///{root}/mlruns.db")
mlflow.set_experiment("ragas-evaluation")
env_file = root / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(root))

from supabase import create_client

from lib.embeddings import get_embedding
from lib.knowledge_retrieval import retrieve_for_chat

supabase = create_client(
    os.environ.get("SUPABASE_URL") or os.environ["VITE_SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)

# Use Ollama locally for judge calls (no API tokens needed)
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:0.5b"

# ---------------------------------------------------------------------------
# Evaluation dataset — 18 queries with ground truth answers
# ---------------------------------------------------------------------------

EVAL_DATASET = [
    {
        "question": "How should I price my product?",
        "ground_truth": "Don't underprice — low prices signal low value. Price is a signal. When one founder raised from $9/month to $49/month, enterprise customers started taking them seriously. Price to reflect the value you deliver, not your costs.",
        "expected_sources": ["Podcast Ep 12: Pricing Strategy"],
    },
    {
        "question": "When should I make my first hire?",
        "ground_truth": "Hire for attitude, train for skill. Your first hire should free up your biggest bottleneck, not fill a role you think you should have. Cultural fit means caring about the same outcomes, not liking the same things.",
        "expected_sources": ["LinkedIn Post: Three Things About Hiring"],
    },
    {
        "question": "How do I know if people want my product?",
        "ground_truth": "You've hit product-market fit when customers start pulling the product out of your hands. Use the 40% test: if 40% of users would be 'very disappointed' if your product disappeared, you're there. If not, keep iterating. Don't scale a leaky bucket.",
        "expected_sources": ["Podcast Ep 27: Product-Market Fit"],
    },
    {
        "question": "How to get customers without spending money?",
        "ground_truth": "Be genuinely helpful in communities where your customers hang out. Write content answering the exact questions customers Google. Ask every happy customer for one introduction. Word of mouth at the early stage beats any paid channel. One founder hit $500K ARR with zero ad spend.",
        "expected_sources": ["Article: Marketing on Zero Budget"],
    },
    {
        "question": "What metrics should I track?",
        "ground_truth": "Before product-market fit, only three metrics matter: retention (are people coming back?), referral (are people telling others?), and revenue per customer (is unit economics viable?). Everything else is vanity.",
        "expected_sources": ["Article: The Only Metrics That Matter"],
    },
    {
        "question": "When should I give up on my idea?",
        "ground_truth": "Most startups don't pivot too late — they pivot too early. Give your idea at least 6 months of genuine effort, meaning actually talking to customers, not building in a vacuum. Be stubborn on vision but flexible on approach.",
        "expected_sources": ["Tweet Thread: When to Pivot"],
    },
    {
        "question": "How to build company culture?",
        "ground_truth": "Culture isn't perks — it's what happens when things go wrong. Do people hide mistakes or share them? Take initiative or wait for permission? Culture is set in the first 10 hires. Every person either reinforces or dilutes your standards.",
        "expected_sources": ["Tweet Thread: Building Culture"],
    },
    {
        "question": "What type of revenue model should I use?",
        "ground_truth": "The main models for early-stage startups are subscription, transaction fees, marketplace commissions, and direct sales. Pick one and focus. The biggest trap is trying to monetise three ways at once before nailing one. Get one revenue stream working reliably first.",
        "expected_sources": ["Podcast Ep 19: Revenue Models"],
    },
    {
        "question": "How to talk to potential customers?",
        "ground_truth": "Never ask people if they'd buy your product — they'll say yes to be polite. Instead, ask about current behaviour: what do they do today, what frustrates them, what have they tried? Past behaviour predicts future behaviour; hypothetical questions predict nothing.",
        "expected_sources": ["Podcast Ep 35: Customer Discovery"],
    },
    {
        "question": "My first market is too broad",
        "ground_truth": "Your first market should be tiny and specific — 'left-handed dentists in Dublin' specific. When you own a niche, you can expand. When you target everyone, you reach no one. Every successful company starts by dominating a small, well-defined segment.",
        "expected_sources": ["LinkedIn Post: Go-To-Market Mistakes"],
    },
    {
        "question": "When should I launch my MVP?",
        "ground_truth": "Your MVP should embarrass you a little. If you're proud of v1, you launched too late. The point isn't to impress — it's to learn as fast as possible. Ship something small, measure what happens, iterate. The winners learn fastest, not build best.",
        "expected_sources": ["Book: The Founder's Playbook, Chapter 3"],
    },
    {
        "question": "Should I take investment or bootstrap?",
        "ground_truth": "Most great businesses never raise VC, and that's fine. VC is a tool, not a trophy. Ask yourself: does my business actually need outside capital, or am I chasing validation? If you can bootstrap to revenue, you keep control and prove the model. That's leverage no pitch deck can match.",
        "expected_sources": ["LinkedIn Post: Fundraising Reality Check"],
    },
    {
        "question": "I'm feeling lonely as a founder",
        "ground_truth": "The hardest part of being a founder is the loneliness — making decisions daily with incomplete information and nobody telling you if you got it right. Build a support system early. Find two or three people who understand the journey and check in regularly. Entrepreneurship is a team sport, even when it feels solo.",
        "expected_sources": ["Podcast Ep 8: Founder Mindset"],
    },
    {
        "question": "How do I charge customers for my product?",
        "ground_truth": "Don't underprice. Low prices signal low value. Price reflects value, not cost. Consider raising prices — one founder went from $9/month to $49/month and started landing enterprise customers who stuck around.",
        "expected_sources": ["Podcast Ep 12: Pricing Strategy"],
    },
    {
        "question": "How do I find my first employees?",
        "ground_truth": "Hire for attitude, train for skill. The best early employees figure things out rather than having perfect CVs. Your first hire should free up your biggest bottleneck. Cultural fit is about caring about the same outcomes.",
        "expected_sources": ["LinkedIn Post: Three Things About Hiring"],
    },
    {
        "question": "How to get my first ten customers?",
        "ground_truth": "The first ten customers are everything. Don't try to scale before manually onboarding at least ten paying customers. Each teaches something your roadmap never could. Call them personally — those conversations shape your product direction. Automation comes later, understanding comes first.",
        "expected_sources": ["Article: Scaling From 0 to 1"],
    },
    {
        "question": "Pricing strategy for startups",
        "ground_truth": "Don't underprice — price signals value. Focus on one revenue model (subscription, transaction fees, marketplace commissions, or direct sales) and nail it before adding complexity.",
        "expected_sources": ["Podcast Ep 12: Pricing Strategy", "Podcast Ep 19: Revenue Models"],
    },
    {
        "question": "Hiring and team culture",
        "ground_truth": "Hire for attitude, train for skill. Your first hire should free your biggest bottleneck. Culture is set in the first 10 hires — it's what happens when things go wrong, not perks. Every hire either reinforces or dilutes your standards.",
        "expected_sources": ["LinkedIn Post: Three Things About Hiring", "Tweet Thread: Building Culture"],
    },
]


# ---------------------------------------------------------------------------
# LLM judge helpers
# ---------------------------------------------------------------------------

def _llm_judge(system_prompt: str, user_prompt: str) -> str:
    response = httpx.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return (response.json().get("message", {}).get("content", "")).strip()


def _parse_json_list(text: str) -> list[str]:
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, (str, int, float))]
        except json.JSONDecodeError:
            pass
    return [s.strip("- ").strip() for s in text.strip().splitlines() if s.strip("- ").strip() and len(s.strip()) > 5]


# ---------------------------------------------------------------------------
# RAGAS metrics
# ---------------------------------------------------------------------------

def context_precision(question: str, chunks: list[dict]) -> float:
    """For each chunk, LLM judges if it's relevant to the question."""
    if not chunks:
        return 0.0

    relevant = 0
    for chunk in chunks:
        response = _llm_judge(
            "You are a relevance judge. Given a question and a text chunk, determine if the chunk contains information relevant to answering the question. Reply with ONLY 'YES' or 'NO'.",
            f"Question: {question}\n\nChunk:\n{chunk['chunk_text']}",
        )
        if response.upper().startswith("YES"):
            relevant += 1

    return relevant / len(chunks)


def context_recall(ground_truth: str, chunks: list[dict]) -> float:
    """Check if key claims from ground truth are covered by retrieved chunks."""
    chunks_text = "\n\n".join(c["chunk_text"] for c in chunks)

    claims_raw = _llm_judge(
        "Extract the key factual claims from the following text. Return a JSON array of strings, one claim per element. Return ONLY the JSON array.",
        f"Text:\n{ground_truth}",
    )
    claims = _parse_json_list(claims_raw)
    if not claims:
        return 0.0

    supported = 0
    for claim in claims:

        response = _llm_judge(
            "You are a fact checker. Given a claim and a body of context, determine if the context supports or contains the claim. Reply with ONLY 'SUPPORTED' or 'NOT SUPPORTED'.",
            f"Claim: {claim}\n\nContext:\n{chunks_text}",
        )
        if "SUPPORTED" in response.upper() and "NOT" not in response.upper():
            supported += 1

    return supported / len(claims)


def faithfulness(answer: str, chunks: list[dict]) -> float:
    """Extract claims from the generated answer, verify each against context."""
    chunks_text = "\n\n".join(c["chunk_text"] for c in chunks)


    claims_raw = _llm_judge(
        "Extract the key factual claims from the following answer. Ignore source citations and conversational filler. Return a JSON array of strings, one claim per element. Return ONLY the JSON array.",
        f"Answer:\n{answer}",
    )
    claims = _parse_json_list(claims_raw)
    if not claims:
        return 1.0  # no claims = nothing to contradict

    supported = 0
    for claim in claims:

        response = _llm_judge(
            "You are a fact checker. Given a claim from a generated answer and the source context, determine if the claim is supported by the context. Reply with ONLY 'SUPPORTED' or 'NOT SUPPORTED'.",
            f"Claim: {claim}\n\nContext:\n{chunks_text}",
        )
        if "SUPPORTED" in response.upper() and "NOT" not in response.upper():
            supported += 1

    return supported / len(claims)


def answer_relevance(question: str, answer: str) -> float:
    """Generate questions the answer would address, compare similarity to original."""

    gen_raw = _llm_judge(
        "Given an answer, generate 3 questions that this answer would be a good response to. Return a JSON array of strings. Return ONLY the JSON array.",
        f"Answer:\n{answer}",
    )
    gen_questions = _parse_json_list(gen_raw)
    if not gen_questions:
        return 0.0

    # Filter to only valid string questions
    gen_questions = [q for q in gen_questions if isinstance(q, str) and len(q) > 5]
    if not gen_questions:
        return 0.0

    original_emb = get_embedding(question)
    similarities = []
    for gq in gen_questions[:3]:
        try:
            gq_emb = get_embedding(gq)
            sim = sum(a * b for a, b in zip(original_emb, gq_emb))
            similarities.append(sim)
        except Exception:
            continue

    return sum(similarities) / len(similarities) if similarities else 0.0


# ---------------------------------------------------------------------------
# Get generated answer from running backend
# ---------------------------------------------------------------------------

def get_chat_answer(question: str, chunks: list[dict]) -> str | None:
    """Generate a short answer locally using Ollama with top 3 retrieved chunks."""
    top_chunks = "\n\n".join(
        f"[{c['source_title']}]: {c['chunk_text'][:300]}" for c in chunks[:3]
    )

    try:
        response = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a startup mentor. Answer based ONLY on the context provided. Keep your answer to 2-3 sentences. Cite sources."},
                    {"role": "user", "content": f"Context:\n{top_chunks}\n\nQuestion: {question}"},
                ],
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 150},
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return (response.json().get("message", {}).get("content", "")).strip()
    except Exception as e:
        print(f"  [warn] Ollama answer generation error: {e}")
    return None


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def evaluate():
    print(f"\nRAGAS Evaluation \u2014 {len(EVAL_DATASET)} test cases")
    print("\u2550" * 60)

    scores = {"context_precision": [], "context_recall": [], "faithfulness": [], "answer_relevance": []}
    source_hits = 0

    for i, tc in enumerate(EVAL_DATASET):
        question = tc["question"]
        ground_truth = tc["ground_truth"]
        expected = tc["expected_sources"]

        print(f"\n[{i+1}/{len(EVAL_DATASET)}] \"{question}\"")

        # Retrieve chunks
        chunks = retrieve_for_chat(supabase, question)
        result_titles = [c["source_title"] for c in chunks]

        # Check source recall
        found = any(e in result_titles for e in expected)
        if found:
            source_hits += 1

        # Get generated answer locally via Ollama
        answer = get_chat_answer(question, chunks)
        if not answer:
            print("  [skip] Could not get answer from /chat endpoint")
            continue

        # Compute RAGAS metrics
        cp = context_precision(question, chunks)
        cr = context_recall(ground_truth, chunks)
        ff = faithfulness(answer, chunks)
        ar = answer_relevance(question, answer)

        scores["context_precision"].append(cp)
        scores["context_recall"].append(cr)
        scores["faithfulness"].append(ff)
        scores["answer_relevance"].append(ar)

        src_mark = "\u2713" if found else "\u2717"
        print(f"  Context Precision:  {cp:.2f}")
        print(f"  Context Recall:     {cr:.2f}")
        print(f"  Faithfulness:       {ff:.2f}")
        print(f"  Answer Relevance:   {ar:.2f}")
        print(f"  Sources: {src_mark} {', '.join(result_titles[:3])}")

    # Aggregate
    print("\n" + "\u2550" * 60)
    print("AGGREGATE SCORES")

    aggregates = {}
    for metric, vals in scores.items():
        if vals:
            avg = sum(vals) / len(vals)
            aggregates[f"avg_{metric}"] = avg
            label = metric.replace("_", " ").title()
            print(f"  {label:24s} {avg:.2f} avg  (n={len(vals)})")

    total = len(EVAL_DATASET)
    aggregates["source_recall"] = source_hits / total
    print(f"  {'Source Recall':24s} {source_hits}/{total} ({source_hits/total*100:.0f}%)")
    print("\u2550" * 60)

    # Log to MLflow
    with mlflow.start_run():
        mlflow.log_params({
            "num_test_cases": len(EVAL_DATASET),
            "ollama_model": OLLAMA_MODEL,
        })
        for name, value in aggregates.items():
            mlflow.log_metric(name, value)


if __name__ == "__main__":
    evaluate()
