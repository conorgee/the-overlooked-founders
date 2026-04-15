"""
Topic Modelling & Knowledge Gap Analysis

Pipeline:
  1. Load all knowledge chunks and embed them
  2. BERTopic clustering with KMeans (small dataset optimised)
  3. UMAP visualisation — 3 views:
     a. Knowledge clusters
     b. Query overlay (where do founder questions land?)
     c. Gap analysis (queries far from any cluster)
  4. Coverage analysis mapping topics to programme weeks
  5. Auto-tag function for new content

Run: python scripts/topic_modelling.py
"""

import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"

import mlflow
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

root = Path(__file__).resolve().parent.parent

mlflow.set_tracking_uri(f"sqlite:///{root}/mlruns.db")
mlflow.set_experiment("topic-modelling")
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

REPORT_DIR = root / "reports"
REPORT_DIR.mkdir(exist_ok=True)

WEEK_TOPICS = {
    1: "idea validation, testing assumptions, talking to customers",
    2: "customer discovery, user interviews, personas",
    3: "business model, revenue models, pricing strategy",
    4: "MVP strategy, minimum viable product, launch",
    5: "go-to-market, marketing, customer acquisition",
    6: "growth metrics, retention, analytics",
    7: "team, hiring, culture building, leadership",
    8: "pitch, fundraising, investors, bootstrapping",
}

TEST_QUERIES = [
    "how do I charge customers for my product",
    "feeling lonely as a founder",
    "should I take investment or bootstrap",
    "how do I find my first employees",
    "how do I know if people want my product",
    "how to get customers without spending money",
    "what metrics should I track",
    "when should I give up on my idea",
    "how to build company culture",
    "what type of revenue model should I use",
    "how to talk to potential customers",
    "my first market is too broad",
    "when should I launch my MVP",
    "how to get my first ten customers",
    "How do I set up a limited company?",
    "What grants are available for young founders?",
    "How do I do market sizing?",
    "How do I manage my cash flow?",
]


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_chunks() -> list[dict]:
    res = (
        supabase.table("knowledge_chunks")
        .select("id, chunk_text, topic_tags, source_document_id, source_documents(title)")
        .order("created_at")
        .execute()
    )
    return [
        {
            "id": r["id"],
            "chunk_text": r["chunk_text"],
            "topic_tags": r.get("topic_tags", []),
            "source_doc_id": r.get("source_document_id"),
            "source_title": (r.get("source_documents") or {}).get("title", "Unknown"),
        }
        for r in (res.data or [])
    ]


# ---------------------------------------------------------------------------
# Topic modelling
# ---------------------------------------------------------------------------

def discover_topics(chunks: list[dict], embeddings: np.ndarray, n_clusters: int = 6):
    print(f"\nStep 2: Topic discovery ({n_clusters} clusters)...")

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    topics = {}
    for i, (chunk, label) in enumerate(zip(chunks, labels)):
        if label not in topics:
            topics[label] = {"chunks": [], "sources": set(), "tags": []}
        topics[label]["chunks"].append(chunk)
        topics[label]["sources"].add(chunk["source_title"])
        topics[label]["tags"].extend(chunk.get("topic_tags") or [])

    print(f"\nTopic Discovery \u2014 {len(chunks)} chunks, {n_clusters} topics")
    print("\u2550" * 60)

    for topic_id in sorted(topics.keys()):
        t = topics[topic_id]
        n_chunks = len(t["chunks"])
        sources = sorted(t["sources"])

        from collections import Counter
        tag_counts = Counter(t["tags"])
        top_tags = [tag for tag, _ in tag_counts.most_common(5)]

        coverage = "STRONG" if n_chunks >= 6 else "MODERATE" if n_chunks >= 4 else "WEAK"

        print(f"\nTopic {topic_id}: ({n_chunks} chunks, {len(sources)} sources)")
        print(f"  Top tags: {', '.join(top_tags)}")
        print(f"  Sources: {', '.join(s[:30] for s in sources)}")
        print(f"  Coverage: {coverage}")

    return labels, topics


# ---------------------------------------------------------------------------
# UMAP visualisation
# ---------------------------------------------------------------------------

def visualise(chunks, embeddings, labels, query_texts, query_embeddings):
    try:
        import umap
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n  [skip] umap-learn or matplotlib not installed. Skipping visualisations.")
        return

    print(f"\nStep 3: UMAP visualisations...")

    reducer = umap.UMAP(n_components=2, random_state=42, metric="cosine", n_neighbors=5)
    coords = reducer.fit_transform(embeddings)

    # View 1: Knowledge clusters
    fig, ax = plt.subplots(figsize=(12, 8))
    scatter = ax.scatter(
        coords[:, 0], coords[:, 1],
        c=labels, cmap="tab10", s=80, alpha=0.7, edgecolors="white", linewidth=0.5,
    )
    for i, c in enumerate(chunks):
        ax.annotate(c["source_title"][:20], (coords[i, 0], coords[i, 1]), fontsize=5, alpha=0.5)
    ax.set_title("Knowledge Base \u2014 Embedding Space (UMAP)")
    plt.colorbar(scatter, label="Topic")
    plt.tight_layout()
    plt.savefig(str(REPORT_DIR / "knowledge_clusters.png"), dpi=150)
    plt.close()
    print(f"  Saved reports/knowledge_clusters.png")

    # View 2: Query overlay
    query_coords = reducer.transform(query_embeddings)

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.scatter(coords[:, 0], coords[:, 1], c=labels, cmap="tab10", s=80, alpha=0.3, label="Knowledge")
    ax.scatter(query_coords[:, 0], query_coords[:, 1], c="red", s=120, marker="x", linewidth=2, label="Queries")
    for i, q in enumerate(query_texts):
        ax.annotate(q[:30], (query_coords[i, 0], query_coords[i, 1]), fontsize=5, color="red")
    ax.set_title("Queries vs Knowledge \u2014 Where Do Founder Questions Land?")
    ax.legend()
    plt.tight_layout()
    plt.savefig(str(REPORT_DIR / "query_overlay.png"), dpi=150)
    plt.close()
    print(f"  Saved reports/query_overlay.png")

    # View 3: Gap analysis
    gaps = find_knowledge_gaps(query_coords, coords, query_texts, chunks)
    return gaps


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------

def find_knowledge_gaps(query_coords, chunk_coords, query_texts, chunks, threshold=2.0):
    print(f"\nStep 4: Knowledge gap analysis...")

    gaps = []
    for i, (qc, qt) in enumerate(zip(query_coords, query_texts)):
        distances = np.sqrt(((chunk_coords - qc) ** 2).sum(axis=1))
        min_dist = distances.min()
        nearest_idx = int(distances.argmin())

        gaps.append({
            "query": qt,
            "distance": float(min_dist),
            "nearest": chunks[nearest_idx]["source_title"],
            "is_gap": min_dist > threshold,
        })

    gaps.sort(key=lambda x: -x["distance"])

    print(f"\nKnowledge Gap Analysis")
    print("\u2550" * 60)

    gap_count = 0
    for g in gaps:
        if g["is_gap"]:
            gap_count += 1
            print(f"  \u26a0 \"{g['query']}\" \u2014 distance {g['distance']:.1f}")
            print(f"    Nearest: {g['nearest']}")

    if gap_count == 0:
        print("  All queries are within range of knowledge clusters.")

    covered = sum(1 for g in gaps if not g["is_gap"])
    print(f"\n  {covered}/{len(gaps)} queries covered, {gap_count} gaps identified")

    return gaps


# ---------------------------------------------------------------------------
# Coverage mapping
# ---------------------------------------------------------------------------

def coverage_analysis(chunks, embeddings, model):
    print(f"\nStep 5: Programme week coverage analysis...")

    week_embeddings = {}
    for week, description in WEEK_TOPICS.items():
        week_embeddings[week] = model.encode([description], normalize_embeddings=True)[0]

    print(f"\nTopic Coverage by Programme Week")
    print("\u2550" * 60)

    for week in sorted(WEEK_TOPICS.keys()):
        week_emb = week_embeddings[week]
        sims = np.dot(embeddings, week_emb)
        relevant = sum(1 for s in sims if s > 0.3)

        bar = "\u2588" * relevant
        coverage = "STRONG" if relevant >= 6 else "MODERATE" if relevant >= 4 else "WEAK"
        flag = " \u26a0" if coverage == "WEAK" else ""

        print(f"  Week {week} ({WEEK_TOPICS[week][:30]:30s}): {relevant:2d} chunks {bar} {coverage}{flag}")


# ---------------------------------------------------------------------------
# Auto-tag function
# ---------------------------------------------------------------------------

def suggest_tags(text: str, model, chunk_embeddings, chunks, labels, top_n: int = 3) -> dict:
    text_emb = model.encode([text], normalize_embeddings=True)[0]
    sims = np.dot(chunk_embeddings, text_emb)

    top_idx = np.argsort(sims)[::-1][:5]
    top_labels = [labels[i] for i in top_idx]

    from collections import Counter
    label_counts = Counter(top_labels)
    primary_topic = label_counts.most_common(1)[0][0]
    confidence = label_counts[primary_topic] / len(top_labels)

    all_tags = []
    for idx in top_idx:
        all_tags.extend(chunks[idx].get("topic_tags") or [])

    tag_counts = Counter(all_tags)
    suggested = [tag for tag, _ in tag_counts.most_common(top_n)]

    return {
        "primary_topic": int(primary_topic),
        "suggested_tags": suggested,
        "confidence": round(confidence, 2),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Topic Modelling & Knowledge Gap Analysis")
    print("=" * 60)

    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks from {len(set(c['source_doc_id'] for c in chunks))} sources")

    print(f"\nStep 1: Embedding chunks...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [c["chunk_text"] for c in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    n_clusters = min(6, len(chunks) // 2)
    labels, topics = discover_topics(chunks, embeddings, n_clusters)

    query_embeddings = model.encode(TEST_QUERIES, normalize_embeddings=True, show_progress_bar=False)
    gaps = visualise(chunks, embeddings, labels, TEST_QUERIES, query_embeddings)

    coverage_analysis(chunks, embeddings, model)

    # Demo auto-tagging
    print(f"\nAuto-Tag Demo:")
    demo_texts = [
        "Angel investors typically look for a 10x return potential. Focus your pitch deck on market size, team, and traction.",
        "The best way to validate your idea is to talk to 50 potential customers before writing a single line of code.",
    ]
    for text in demo_texts:
        result = suggest_tags(text, model, embeddings, chunks, labels)
        print(f"  \"{text[:60]}...\"")
        print(f"    Topic {result['primary_topic']}, Tags: {result['suggested_tags']}, Confidence: {result['confidence']}")

    # Log to MLflow
    with mlflow.start_run():
        mlflow.log_params({
            "num_chunks": len(chunks),
            "n_clusters": n_clusters,
            "num_test_queries": len(TEST_QUERIES),
        })
        mlflow.log_metric("num_gaps", sum(1 for g in (gaps or []) if g.get("is_gap")))
        mlflow.log_metric("num_topics", len(topics))

        # Log UMAP visualisations as artifacts
        for png in REPORT_DIR.glob("*.png"):
            mlflow.log_artifact(str(png))

    print("\nDone.")


if __name__ == "__main__":
    main()
