"""
Fine-Tune Embedding Model on Startup Domain Data

Pipeline:
  1. Generate synthetic (query, passage) pairs from knowledge chunks via Ollama
  2. Generate hard negatives (similar but wrong chunks)
  3. Quality filter: deduplicate, length check, relevance check
  4. Train with TripletLoss + GroupKFold by source document
  5. Compare fine-tuned vs base model on held-out test queries

Run: python scripts/finetune_embeddings.py
"""

import json
import math
import os
import re
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"

import httpx
import mlflow
import numpy as np
from sentence_transformers import SentenceTransformer, InputExample, losses, evaluation
from sklearn.model_selection import GroupKFold
from torch.utils.data import DataLoader

root = Path(__file__).resolve().parent.parent

mlflow.set_tracking_uri(f"sqlite:///{root}/mlruns.db")
mlflow.set_experiment("embedding-finetuning")
env_file = root / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(root))

from supabase import create_client
from lib.embeddings import get_embedding

supabase = create_client(
    os.environ.get("SUPABASE_URL") or os.environ["VITE_SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:0.5b"
OUTPUT_DIR = str(root / "models" / "startup-embeddings-v1")

GENERATION_PROMPTS = {
    "direct": (
        "Generate 3 questions that this passage directly answers. "
        "Return ONLY a JSON array of 3 question strings."
    ),
    "paraphrase": (
        "Generate 3 questions that ask for the same information but use "
        "completely different vocabulary. Avoid any words from the passage. "
        "Return ONLY a JSON array of 3 question strings."
    ),
    "casual": (
        "Generate 3 questions a 19-year-old first-time founder might ask in "
        "casual language. Return ONLY a JSON array of 3 question strings."
    ),
    "jargon": (
        "Generate 3 questions using startup/VC jargon that this passage answers. "
        "Return ONLY a JSON array of 3 question strings."
    ),
    "adjacent": (
        "Generate 3 questions where this passage is partially relevant. "
        "Return ONLY a JSON array of 3 question strings."
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ollama_generate(prompt: str) -> str:
    response = httpx.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.8, "num_predict": 200},
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json().get("message", {}).get("content", "").strip()


def parse_json_list(text: str) -> list[str]:
    match = re.search(r"\[[\s\S]*?\]", text)
    if match:
        try:
            parsed = json.loads(match.group())
            return [str(x) for x in parsed if isinstance(x, (str, int, float))]
        except json.JSONDecodeError:
            pass
    return [s.strip("- ").strip() for s in text.splitlines() if s.strip("- ").strip() and len(s.strip()) > 10]


def cosine_sim(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


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
            "source_doc_id": r.get("source_document_id"),
            "source_title": (r.get("source_documents") or {}).get("title", "Unknown"),
        }
        for r in (res.data or [])
    ]


# ---------------------------------------------------------------------------
# Step 1: Generate synthetic queries
# ---------------------------------------------------------------------------

def generate_queries(chunks: list[dict]) -> list[dict]:
    print(f"\nStep 1: Generating synthetic queries for {len(chunks)} chunks...")
    pairs = []

    for i, chunk in enumerate(chunks):
        for style, prompt_template in GENERATION_PROMPTS.items():
            prompt = f"{prompt_template}\n\nPassage:\n{chunk['chunk_text'][:500]}"
            raw = ollama_generate(prompt)
            questions = parse_json_list(raw)

            for q in questions[:3]:
                if len(q.split()) >= 3:
                    pairs.append({
                        "query": q,
                        "positive": chunk["chunk_text"],
                        "source_doc_id": chunk["source_doc_id"],
                        "source_title": chunk["source_title"],
                        "style": style,
                    })

        if (i + 1) % 5 == 0:
            print(f"  {i+1}/{len(chunks)} chunks processed ({len(pairs)} pairs so far)")

    print(f"  Generated {len(pairs)} raw (query, passage) pairs")
    return pairs


# ---------------------------------------------------------------------------
# Step 2: Generate hard negatives
# ---------------------------------------------------------------------------

def add_hard_negatives(pairs: list[dict], chunks: list[dict]) -> list[dict]:
    print(f"\nStep 2: Computing hard negatives...")

    chunk_embeddings = {}
    for c in chunks:
        chunk_embeddings[c["id"]] = get_embedding(c["chunk_text"])

    triplets = []
    for i, pair in enumerate(pairs):
        query_emb = get_embedding(pair["query"])
        positive_text = pair["positive"]

        similarities = []
        for c in chunks:
            if c["chunk_text"] == positive_text:
                continue
            sim = cosine_sim(query_emb, chunk_embeddings[c["id"]])
            similarities.append((c["chunk_text"], sim))

        similarities.sort(key=lambda x: -x[1])
        hard_neg = similarities[0][0] if similarities else chunks[0]["chunk_text"]

        triplets.append({**pair, "hard_negative": hard_neg})

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(pairs)} pairs processed")

    print(f"  Created {len(triplets)} triplets with hard negatives")
    return triplets


# ---------------------------------------------------------------------------
# Step 3: Quality filtering
# ---------------------------------------------------------------------------

def filter_pairs(triplets: list[dict]) -> list[dict]:
    print(f"\nStep 3: Quality filtering {len(triplets)} triplets...")

    filtered = []
    seen_embeddings = []

    for t in triplets:
        query = t["query"]

        if len(query.split()) < 3:
            continue

        query_emb = get_embedding(query)

        is_dup = any(cosine_sim(query_emb, seen) > 0.92 for seen in seen_embeddings)
        if is_dup:
            continue

        passage_emb = get_embedding(t["positive"])
        if cosine_sim(query_emb, passage_emb) < 0.05:
            continue

        seen_embeddings.append(query_emb)
        filtered.append(t)

    print(f"  {len(triplets)} -> {len(filtered)} after filtering ({len(triplets) - len(filtered)} removed)")
    return filtered


# ---------------------------------------------------------------------------
# Step 4: Train with GroupKFold
# ---------------------------------------------------------------------------

def train(triplets: list[dict], chunks: list[dict]):
    print(f"\nStep 4: Training with {len(triplets)} triplets...")

    source_ids = list(set(t["source_doc_id"] for t in triplets))
    groups = [t["source_doc_id"] for t in triplets]

    n_splits = min(3, len(source_ids))
    if n_splits < 2:
        print("  Not enough source documents for cross-validation. Training on all data.")
        n_splits = None

    best_mrr = 0
    best_fold = -1

    if n_splits:
        gkf = GroupKFold(n_splits=n_splits)
        dummy_X = np.zeros(len(triplets))

        for fold, (train_idx, val_idx) in enumerate(gkf.split(dummy_X, groups=groups)):
            print(f"\n  Fold {fold+1}/{n_splits}: {len(train_idx)} train, {len(val_idx)} val")

            model = SentenceTransformer("all-MiniLM-L6-v2")

            train_examples = [
                InputExample(texts=[triplets[i]["query"], triplets[i]["positive"], triplets[i]["hard_negative"]])
                for i in train_idx
            ]

            train_loader = DataLoader(train_examples, shuffle=True, batch_size=16)
            train_loss = losses.TripletLoss(
                model=model,
                distance_metric=losses.TripletDistanceMetric.COSINE,
                triplet_margin=0.2,
            )

            val_queries = {str(i): triplets[idx]["query"] for i, idx in enumerate(val_idx)}
            corpus = {str(i): c["chunk_text"] for i, c in enumerate(chunks)}

            relevant = {}
            for i, idx in enumerate(val_idx):
                positive_text = triplets[idx]["positive"]
                for j, c in enumerate(chunks):
                    if c["chunk_text"] == positive_text:
                        relevant[str(i)] = {str(j)}
                        break

            val_evaluator = evaluation.InformationRetrievalEvaluator(
                queries=val_queries,
                corpus=corpus,
                relevant_docs=relevant,
                name=f"fold{fold}",
                mrr_at_k=[5, 8],
                ndcg_at_k=[5, 8],
                accuracy_at_k=[1, 3, 5],
            )

            fold_output = str(root / "models" / f"fold{fold}")

            model.fit(
                train_objectives=[(train_loader, train_loss)],
                evaluator=val_evaluator,
                evaluation_steps=50,
                epochs=5,
                warmup_steps=max(1, int(len(train_examples) * 0.1)),
                output_path=fold_output,
                save_best_model=True,
            )

            metrics = val_evaluator(model, output_path=fold_output)
            mrr = metrics.get(f"fold{fold}_cosine_mrr@8", 0)
            ndcg = metrics.get(f"fold{fold}_cosine_ndcg@8", 0)
            print(f"  Fold {fold+1}: MRR@8={mrr:.3f}, NDCG@8={ndcg:.3f}")

            if mrr > best_mrr:
                best_mrr = mrr
                best_fold = fold

    # Final training on all data
    print(f"\n  Training final model on all {len(triplets)} triplets...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    all_examples = [
        InputExample(texts=[t["query"], t["positive"], t["hard_negative"]])
        for t in triplets
    ]
    all_loader = DataLoader(all_examples, shuffle=True, batch_size=16)
    all_loss = losses.TripletLoss(
        model=model,
        distance_metric=losses.TripletDistanceMetric.COSINE,
        triplet_margin=0.2,
    )

    model.fit(
        train_objectives=[(all_loader, all_loss)],
        epochs=3,
        warmup_steps=max(1, int(len(all_examples) * 0.1)),
        output_path=OUTPUT_DIR,
    )

    print(f"  Model saved to {OUTPUT_DIR}")
    return model


# ---------------------------------------------------------------------------
# Step 5: Compare base vs fine-tuned
# ---------------------------------------------------------------------------

TEST_QUERIES = [
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
]


def benchmark_model(model: SentenceTransformer, chunks: list[dict]) -> dict:
    chunk_texts = [c["chunk_text"] for c in chunks]
    chunk_embs = model.encode(chunk_texts, normalize_embeddings=True)

    mrrs, ndcgs, recalls = [], [], []

    for tc in TEST_QUERIES:
        q_emb = model.encode([tc["query"]], normalize_embeddings=True)[0]
        sims = np.dot(chunk_embs, q_emb)
        ranked = np.argsort(sims)[::-1]
        ranked_titles = [chunks[i]["source_title"] for i in ranked]

        expected = tc["expects"]
        for rank, title in enumerate(ranked_titles):
            if title in expected:
                mrrs.append(1.0 / (rank + 1))
                break
        else:
            mrrs.append(0.0)

        recall = int(any(e in ranked_titles[:8] for e in expected))
        recalls.append(recall)

        dcg = sum(
            (1.0 if ranked_titles[i] in expected else 0.0) / math.log2(i + 2)
            for i in range(8)
        )
        ideal = sorted([1.0 if t in expected else 0.0 for t in ranked_titles[:8]], reverse=True)
        idcg = sum(r / math.log2(i + 2) for i, r in enumerate(ideal))
        ndcgs.append(dcg / idcg if idcg > 0 else 0.0)

    return {
        "MRR": np.mean(mrrs),
        "NDCG@8": np.mean(ndcgs),
        "Recall@8": np.mean(recalls),
    }


def compare(tuned_model: SentenceTransformer, chunks: list[dict]):
    print(f"\nStep 5: Comparing base vs fine-tuned model...")

    base_model = SentenceTransformer("all-MiniLM-L6-v2")
    base_scores = benchmark_model(base_model, chunks)
    tuned_scores = benchmark_model(tuned_model, chunks)

    print(f"\n{'':25s} {'MRR':>7s} {'NDCG@8':>8s} {'Recall@8':>9s}")
    print("\u2500" * 55)
    print(f"{'all-MiniLM-L6-v2 (base)':25s} {base_scores['MRR']:>7.3f} {base_scores['NDCG@8']:>8.3f} {base_scores['Recall@8']:>9.3f}")
    print(f"{'startup-embed-v1 (tuned)':25s} {tuned_scores['MRR']:>7.3f} {tuned_scores['NDCG@8']:>8.3f} {tuned_scores['Recall@8']:>9.3f}")

    if base_scores["MRR"] > 0:
        mrr_pct = (tuned_scores["MRR"] - base_scores["MRR"]) / base_scores["MRR"] * 100
        ndcg_pct = (tuned_scores["NDCG@8"] - base_scores["NDCG@8"]) / base_scores["NDCG@8"] * 100
        print(f"\n  MRR change:  {mrr_pct:+.1f}%")
        print(f"  NDCG change: {ndcg_pct:+.1f}%")

        if tuned_scores["MRR"] > base_scores["MRR"]:
            print(f"\n  Fine-tuned model improves retrieval. Saved to {OUTPUT_DIR}")
            print(f"  To deploy: set EMBEDDING_MODEL={OUTPUT_DIR} and re-run seed_knowledge.py")
        else:
            print(f"\n  Base model performs equally or better. Fine-tuning didn't help.")
            print(f"  This is a valid finding — the base model is already good for this domain.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Embedding Fine-Tuning Pipeline")
    print("=" * 60)

    chunks = load_chunks()
    print(f"Loaded {len(chunks)} knowledge chunks from {len(set(c['source_doc_id'] for c in chunks))} sources")

    pairs = generate_queries(chunks)
    triplets = add_hard_negatives(pairs, chunks)
    filtered = filter_pairs(triplets)

    if len(filtered) < 10:
        print(f"\nOnly {len(filtered)} training triplets after filtering. Need at least 10.")
        return

    with mlflow.start_run():
        mlflow.log_params({
            "base_model": "all-MiniLM-L6-v2",
            "num_chunks": len(chunks),
            "num_triplets": len(filtered),
            "triplet_margin": 0.2,
            "epochs": 3,
            "batch_size": 16,
        })

        tuned_model = train(filtered, chunks)
        compare(tuned_model, chunks)

        mlflow.log_artifact(OUTPUT_DIR)

    print("\nDone.")


if __name__ == "__main__":
    main()
