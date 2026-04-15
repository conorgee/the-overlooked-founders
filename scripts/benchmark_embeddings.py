"""
Embedding Model Benchmark
Compares 4 embedding models on the knowledge base using IR metrics:
  - Recall@3, @5, @8
  - MRR (Mean Reciprocal Rank)
  - NDCG@8
  - Average cosine similarity

Runs entirely in-memory — no database writes needed.
Run: python scripts/benchmark_embeddings.py
"""

import json
import math
import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"

import mlflow
import numpy as np
from sentence_transformers import SentenceTransformer

root = Path(__file__).resolve().parent.parent

mlflow.set_tracking_uri(f"sqlite:///{root}/mlruns.db")
mlflow.set_experiment("embedding-benchmark")
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

# ---------------------------------------------------------------------------
# Models to benchmark (all 384-dim, drop-in replacements)
# ---------------------------------------------------------------------------

MODELS = [
    {"name": "all-MiniLM-L6-v2", "id": "sentence-transformers/all-MiniLM-L6-v2", "note": "current baseline"},
    {"name": "bge-small-en-v1.5", "id": "BAAI/bge-small-en-v1.5", "note": "MTEB top-ranked"},
    {"name": "e5-small-v2", "id": "intfloat/e5-small-v2", "note": "strong on short queries"},
    {"name": "gte-small", "id": "thenlper/gte-small", "note": "newest, smallest"},
]

# ---------------------------------------------------------------------------
# Test cases (reuse from eval_retrieval.py)
# ---------------------------------------------------------------------------

TEST_CASES = [
    {"query": "how do I charge customers for my product", "expects": ["Podcast Ep 12: Pricing Strategy"]},
    {"query": "feeling lonely as a founder", "expects": ["Podcast Ep 8: Founder Mindset"]},
    {"query": "should I take investment or bootstrap", "expects": ["LinkedIn Post: Fundraising Reality Check"]},
    {"query": "how do I find my first employees", "expects": ["LinkedIn Post: Three Things About Hiring"]},
    {"query": "how do I know if people want my product", "expects": ["Podcast Ep 27: Product-Market Fit"]},
    {"query": "how to get customers without spending money", "expects": ["Article: Marketing on Zero Budget"]},
    {"query": "what metrics should I track", "expects": ["Article: The Only Metrics That Matter"]},
    {"query": "when should I give up on my idea", "expects": ["Tweet Thread: When to Pivot"]},
    {"query": "how to build company culture", "expects": ["Tweet Thread: Building Culture"]},
    {"query": "what type of revenue model should I use", "expects": ["Podcast Ep 19: Revenue Models"]},
    {"query": "how to talk to potential customers", "expects": ["Podcast Ep 35: Customer Discovery"]},
    {"query": "my first market is too broad", "expects": ["LinkedIn Post: Go-To-Market Mistakes"]},
    {"query": "when should I launch my MVP", "expects": ["Book: The Founder's Playbook, Chapter 3"]},
    {"query": "how to get my first ten customers", "expects": ["Article: Scaling From 0 to 1"]},
    {"query": "pricing strategy for startups", "expects": ["Podcast Ep 12: Pricing Strategy", "Podcast Ep 19: Revenue Models"]},
    {"query": "hiring and team culture", "expects": ["LinkedIn Post: Three Things About Hiring", "Tweet Thread: Building Culture"]},
    {"query": "How should I price my product?", "expects": ["Podcast Ep 12: Pricing Strategy"]},
    {"query": "When should I make my first hire?", "expects": ["LinkedIn Post: Three Things About Hiring"]},
]


# ---------------------------------------------------------------------------
# IR metrics
# ---------------------------------------------------------------------------

def recall_at_k(ranked_titles: list[str], expected: list[str], k: int) -> float:
    top_k = ranked_titles[:k]
    found = sum(1 for e in expected if e in top_k)
    return found / len(expected)


def mrr(ranked_titles: list[str], expected: list[str]) -> float:
    for rank, title in enumerate(ranked_titles):
        if title in expected:
            return 1.0 / (rank + 1)
    return 0.0


def ndcg_at_k(ranked_titles: list[str], expected: list[str], k: int) -> float:
    dcg = 0.0
    for i, title in enumerate(ranked_titles[:k]):
        rel = 1.0 if title in expected else 0.0
        dcg += rel / math.log2(i + 2)

    ideal_rels = sorted(
        [1.0 if title in expected else 0.0 for title in ranked_titles[:k]],
        reverse=True,
    )
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal_rels))

    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Load knowledge chunks from Supabase
# ---------------------------------------------------------------------------

def load_chunks() -> list[dict]:
    res = (
        supabase.table("knowledge_chunks")
        .select("id, chunk_text, source_document_id, source_documents(title)")
        .order("created_at")
        .execute()
    )
    return [
        {
            "id": r["id"],
            "chunk_text": r["chunk_text"],
            "source_title": (r.get("source_documents") or {}).get("title", "Unknown"),
            "source_doc_id": r.get("source_document_id"),
        }
        for r in (res.data or [])
    ]


# ---------------------------------------------------------------------------
# Benchmark a single model
# ---------------------------------------------------------------------------

def benchmark_model(model: SentenceTransformer, chunks: list[dict], prefix: str = "") -> dict:
    chunk_texts = [prefix + c["chunk_text"] for c in chunks]
    chunk_embeddings = model.encode(chunk_texts, normalize_embeddings=True, show_progress_bar=False)

    metrics = {"recall@3": [], "recall@5": [], "recall@8": [], "mrr": [], "ndcg@8": [], "avg_sim": []}

    for tc in TEST_CASES:
        query_text = prefix + tc["query"]
        query_emb = model.encode([query_text], normalize_embeddings=True, show_progress_bar=False)[0]

        similarities = np.dot(chunk_embeddings, query_emb)
        ranked_indices = np.argsort(similarities)[::-1]

        ranked_titles = [chunks[i]["source_title"] for i in ranked_indices]
        top_sims = [float(similarities[i]) for i in ranked_indices[:8]]

        expected = tc["expects"]

        metrics["recall@3"].append(recall_at_k(ranked_titles, expected, 3))
        metrics["recall@5"].append(recall_at_k(ranked_titles, expected, 5))
        metrics["recall@8"].append(recall_at_k(ranked_titles, expected, 8))
        metrics["mrr"].append(mrr(ranked_titles, expected))
        metrics["ndcg@8"].append(ndcg_at_k(ranked_titles, expected, 8))
        metrics["avg_sim"].append(sum(top_sims) / len(top_sims))

    return {k: sum(v) / len(v) for k, v in metrics.items()}


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------

def benchmark():
    print("\nLoading knowledge chunks from Supabase...")
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks\n")

    print(f"Embedding Model Benchmark \u2014 {len(TEST_CASES)} queries \u00d7 {len(MODELS)} models")
    print("\u2550" * 80)

    results = {}

    for m in MODELS:
        print(f"\nLoading {m['name']} ({m['note']})...")
        model = SentenceTransformer(m["id"])

        # e5 models need "query: " prefix for queries
        prefix = "query: " if "e5" in m["id"] else ""

        scores = benchmark_model(model, chunks, prefix)
        results[m["name"]] = scores
        print(f"  Done \u2014 MRR: {scores['mrr']:.3f}, NDCG@8: {scores['ndcg@8']:.3f}")

        # Log to MLflow
        with mlflow.start_run(run_name=m["name"]):
            mlflow.log_params({"model_name": m["name"], "model_id": m["id"], "num_test_cases": len(TEST_CASES), "num_chunks": len(chunks)})
            for metric_name, value in scores.items():
                mlflow.log_metric(metric_name.replace("@", "_at_"), value)

        # Free memory
        del model

    # Print comparison table
    print("\n" + "\u2550" * 80)
    header = f"{'Model':<22s} {'Recall@3':>9s} {'Recall@5':>9s} {'Recall@8':>9s} {'MRR':>7s} {'NDCG@8':>8s} {'AvgSim':>8s}"
    print(header)
    print("\u2500" * 80)

    for name, scores in results.items():
        print(
            f"{name:<22s} {scores['recall@3']:>9.3f} {scores['recall@5']:>9.3f} "
            f"{scores['recall@8']:>9.3f} {scores['mrr']:>7.3f} {scores['ndcg@8']:>8.3f} "
            f"{scores['avg_sim']:>8.3f}"
        )

    print("\u2550" * 80)

    # Find winner by MRR
    winner = max(results.items(), key=lambda x: x[1]["mrr"])
    baseline = results.get("all-MiniLM-L6-v2", {})

    print(f"\nWinner: {winner[0]}")
    if baseline and winner[0] != "all-MiniLM-L6-v2":
        mrr_diff = (winner[1]["mrr"] - baseline["mrr"]) / baseline["mrr"] * 100
        ndcg_diff = (winner[1]["ndcg@8"] - baseline["ndcg@8"]) / baseline["ndcg@8"] * 100
        print(f"  {mrr_diff:+.1f}% MRR over current model (all-MiniLM-L6-v2)")
        print(f"  {ndcg_diff:+.1f}% NDCG@8")
        print(f"  Same dimensionality (384) \u2014 drop-in replacement")
        print(f"\nRecommendation: Switch to {winner[0]} and re-embed knowledge base.")
    elif winner[0] == "all-MiniLM-L6-v2":
        print("  Current model is the best choice for this domain.")
        print("  No model swap needed \u2014 choice validated with data.")

    print()


if __name__ == "__main__":
    benchmark()
