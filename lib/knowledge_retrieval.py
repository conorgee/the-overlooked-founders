"""
Shared knowledge retrieval module for RAG.
Hybrid search: pgvector semantic similarity + PostgreSQL full-text search.
Results merged via Reciprocal Rank Fusion, then deduplicated by source.
"""

from lib.embeddings import get_embedding

RRF_K = 60

WEEK_TOPIC_MAP = {
    1: "idea validation, testing assumptions, talking to customers, product-market fit, pivoting",
    2: "customer discovery, user interviews, customer personas, pain point mapping, research",
    3: "business model, revenue models, pricing strategy, unit economics, monetisation",
    4: "MVP strategy, minimum viable product, feature prioritisation, build vs buy, iteration, launch",
    5: "go-to-market strategy, marketing, customer acquisition, growth channels, niche, launch planning",
    6: "growth metrics, retention, analytics, KPIs, scaling, data-driven decisions",
    7: "team and operations, hiring, first hires, culture building, leadership, delegation",
    8: "pitch and next steps, fundraising, investors, bootstrapping, 90-day plan",
}


def retrieve_for_chat(supabase, user_message: str, limit: int = 8) -> list[dict]:
    try:
        embedding = get_embedding(user_message)

        vector_res = supabase.rpc(
            "match_knowledge",
            {"query_embedding": embedding, "match_count": limit, "match_threshold": 0.15},
        ).execute()

        keyword_res = supabase.rpc(
            "keyword_search",
            {"search_query": user_message, "match_count": limit},
        ).execute()

        vector_hits = [_map_rpc_result(r) for r in (vector_res.data or [])]
        keyword_hits = [_map_keyword_result(r) for r in (keyword_res.data or [])]

        merged = _merge_and_rank(vector_hits, keyword_hits)
        deduped = _deduplicate_sources(merged, 2)
        boosted = _apply_feedback_boost(deduped, supabase)

        if len(boosted) >= 3:
            return boosted[:limit]
    except Exception as e:
        print(f"[retrieval] Hybrid search failed, falling back: {e}")

    return _get_all_chunks(supabase)


def retrieve_for_week(supabase, week_number: int, limit: int = 6) -> list[dict]:
    week_description = WEEK_TOPIC_MAP.get(week_number)

    if week_description:
        try:
            embedding = get_embedding(week_description)

            res = supabase.rpc(
                "match_knowledge",
                {"query_embedding": embedding, "match_count": limit * 2, "match_threshold": 0.15},
            ).execute()

            if res.data and len(res.data) >= 3:
                mapped = [_map_rpc_result(r) for r in res.data]
                deduped = _deduplicate_sources(mapped, 2)
                return deduped[:limit]
        except Exception as e:
            print(f"[retrieval] Vector search failed for week, falling back: {e}")

    return _get_all_chunks(supabase)


def format_chunks_for_prompt(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"[SOURCE: {c['source_title']}]\n{c['chunk_text']}" for c in chunks
    )


def _merge_and_rank(vector_hits: list[dict], keyword_hits: list[dict]) -> list[dict]:
    score_map = {}

    for rank, hit in enumerate(vector_hits):
        key = hit["id"]
        score = 1 / (RRF_K + rank + 1)
        score_map[key] = {**hit, "rrf_score": score}

    for rank, hit in enumerate(keyword_hits):
        key = hit["id"]
        score = 1 / (RRF_K + rank + 1)
        if key in score_map:
            score_map[key]["rrf_score"] += score
        else:
            score_map[key] = {**hit, "rrf_score": score}

    return sorted(score_map.values(), key=lambda x: x["rrf_score"], reverse=True)


def _deduplicate_sources(results: list[dict], max_per_source: int = 2) -> list[dict]:
    counts: dict[str, int] = {}
    out = []
    for r in results:
        key = r.get("source_doc_id", "")
        if not key:
            out.append(r)
            continue
        counts[key] = counts.get(key, 0) + 1
        if counts[key] <= max_per_source:
            out.append(r)
    return out


def _apply_feedback_boost(results: list[dict], supabase) -> list[dict]:
    """Adjust RRF scores based on chunk quality feedback. +/-15% after 5+ ratings."""
    chunk_ids = [r["id"] for r in results if r.get("id")]
    if not chunk_ids:
        return results

    try:
        quality_res = supabase.table("chunk_quality").select("*").in_(
            "chunk_id", chunk_ids
        ).execute()

        quality_map = {q["chunk_id"]: q for q in (quality_res.data or [])}

        for r in results:
            q = quality_map.get(r.get("id"))
            if not q:
                continue
            total = q["helpful_count"] + q["not_helpful_count"]
            if total < 5:
                continue
            boost = (q["wilson_score"] - 0.5) * 0.3
            if "rrf_score" in r:
                r["rrf_score"] *= (1 + boost)

        results.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)
    except Exception:
        pass  # chunk_quality table may not exist yet

    return results


def _get_all_chunks(supabase) -> list[dict]:
    res = (
        supabase.table("knowledge_chunks")
        .select("id, chunk_text, topic_tags, source_document_id, source_documents(title, source_type)")
        .order("created_at")
        .execute()
    )
    return [
        {
            "id": r["id"],
            "chunk_text": r["chunk_text"],
            "topic_tags": r["topic_tags"],
            "source_title": (r.get("source_documents") or {}).get("title", "Unknown"),
            "source_type": (r.get("source_documents") or {}).get("source_type", "unknown"),
            "source_doc_id": r.get("source_document_id"),
        }
        for r in (res.data or [])
    ]


def _map_rpc_result(r: dict) -> dict:
    return {
        "id": r["id"],
        "chunk_text": r["chunk_text"],
        "topic_tags": r.get("topic_tags"),
        "source_title": r.get("source_title", "Unknown"),
        "source_type": r.get("source_type", "unknown"),
        "source_doc_id": r.get("source_doc_id"),
        "similarity": r.get("similarity"),
    }


def _map_keyword_result(r: dict) -> dict:
    return {
        "id": r["id"],
        "chunk_text": r["chunk_text"],
        "topic_tags": r.get("topic_tags"),
        "source_title": r.get("source_title", "Unknown"),
        "source_type": r.get("source_type", "unknown"),
        "source_doc_id": r.get("source_doc_id"),
        "rank": r.get("rank"),
    }
