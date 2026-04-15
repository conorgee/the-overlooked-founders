"""
Feedback Analytics Report

Analyses chat feedback data to identify:
  1. Overall feedback stats (helpful ratio, feedback rate)
  2. Chunk quality leaderboard (best/worst by Wilson score)
  3. Feedback by source document
  4. Knowledge gaps from downvoted low-similarity responses

Run: python scripts/feedback_analytics.py
"""

import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"

root = Path(__file__).resolve().parent.parent
env_file = root / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(root))

from supabase import create_client

supabase = create_client(
    os.environ.get("SUPABASE_URL") or os.environ["VITE_SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)


def main():
    print("=" * 60)
    print("Feedback Analytics Report")
    print("=" * 60)

    # 1. Overall stats
    all_messages = (
        supabase.table("chat_messages")
        .select("id, role, feedback")
        .eq("role", "assistant")
        .execute()
    )
    assistant_msgs = all_messages.data or []
    total = len(assistant_msgs)
    with_feedback = [m for m in assistant_msgs if m.get("feedback")]
    helpful = sum(1 for m in with_feedback if m["feedback"] == "helpful")
    not_helpful = sum(1 for m in with_feedback if m["feedback"] == "not_helpful")

    print(f"\nOverall Stats")
    print("\u2550" * 60)
    print(f"  Total assistant messages:  {total}")
    print(f"  With feedback:             {len(with_feedback)} ({len(with_feedback)/max(total,1)*100:.0f}%)")
    if with_feedback:
        print(f"  Helpful:                   {helpful} ({helpful/len(with_feedback)*100:.0f}%)")
        print(f"  Not helpful:               {not_helpful} ({not_helpful/len(with_feedback)*100:.0f}%)")

    # 2. Chunk quality leaderboard
    quality_res = (
        supabase.table("chunk_quality")
        .select("*, knowledge_chunks(chunk_text, source_document_id, source_documents(title))")
        .order("wilson_score", desc=True)
        .execute()
    )
    quality_data = quality_res.data or []

    rated = [q for q in quality_data if q["helpful_count"] + q["not_helpful_count"] >= 3]

    if rated:
        print(f"\nChunk Quality Leaderboard (min 3 ratings)")
        print("\u2550" * 60)

        print(f"\n  Best:")
        for q in rated[:5]:
            kc = q.get("knowledge_chunks") or {}
            title = (kc.get("source_documents") or {}).get("title", "Unknown")
            text_preview = (kc.get("chunk_text") or "")[:50]
            total_r = q["helpful_count"] + q["not_helpful_count"]
            print(f"    {q['wilson_score']:.2f}  {title[:35]:35s}  ({q['helpful_count']}\u2191 {q['not_helpful_count']}\u2193, n={total_r})")

        worst = sorted(rated, key=lambda x: x["wilson_score"])
        if worst and worst[0]["wilson_score"] < 0.5:
            print(f"\n  Worst:")
            for q in worst[:5]:
                kc = q.get("knowledge_chunks") or {}
                title = (kc.get("source_documents") or {}).get("title", "Unknown")
                total_r = q["helpful_count"] + q["not_helpful_count"]
                print(f"    {q['wilson_score']:.2f}  {title[:35]:35s}  ({q['helpful_count']}\u2191 {q['not_helpful_count']}\u2193, n={total_r})")
    else:
        print(f"\n  No chunks with 3+ ratings yet.")

    # 3. Feedback by source document
    retrieval_res = (
        supabase.table("retrieval_logs")
        .select("chunk_id, message_id, chat_messages(feedback), knowledge_chunks(source_documents(title))")
        .execute()
    )
    retrieval_data = retrieval_res.data or []

    source_stats: dict[str, dict] = {}
    for r in retrieval_data:
        feedback = (r.get("chat_messages") or {}).get("feedback")
        if not feedback:
            continue
        title = ((r.get("knowledge_chunks") or {}).get("source_documents") or {}).get("title", "Unknown")
        if title not in source_stats:
            source_stats[title] = {"helpful": 0, "not_helpful": 0}
        if feedback == "helpful":
            source_stats[title]["helpful"] += 1
        else:
            source_stats[title]["not_helpful"] += 1

    if source_stats:
        print(f"\nFeedback by Source Document")
        print("\u2550" * 60)
        sorted_sources = sorted(
            source_stats.items(),
            key=lambda x: x[1]["helpful"] / max(x[1]["helpful"] + x[1]["not_helpful"], 1),
            reverse=True,
        )
        for title, stats in sorted_sources:
            total_s = stats["helpful"] + stats["not_helpful"]
            ratio = stats["helpful"] / total_s * 100
            print(f"  {ratio:5.0f}%  {title[:40]:40s}  ({stats['helpful']}\u2191 {stats['not_helpful']}\u2193)")

    # Log to MLflow if available
    try:
        import mlflow
        mlflow.set_tracking_uri(f"sqlite:///{root}/mlruns.db")
        mlflow.set_experiment("feedback-analytics")
        with mlflow.start_run():
            mlflow.log_metrics({
                "total_messages": total,
                "feedback_count": len(with_feedback),
                "helpful_count": helpful,
                "not_helpful_count": not_helpful,
                "feedback_rate": len(with_feedback) / max(total, 1),
                "helpful_ratio": helpful / max(len(with_feedback), 1),
            })
    except Exception:
        pass

    print("\nDone.")


if __name__ == "__main__":
    main()
