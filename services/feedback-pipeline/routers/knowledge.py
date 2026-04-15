import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import supabase, authenticate
from lib.chunker import chunk_text
from lib.embeddings import get_embedding

logger = logging.getLogger(__name__)
router = APIRouter()


class IngestBody(BaseModel):
    title: str
    content: str
    sourceType: str = "article"
    sourceUrl: str | None = None
    topicTags: list[str] = []


def _build_chunk_rows(content: str, source_doc_id: str, topic_tags: list[str], source_type: str) -> list[dict]:
    chunks = chunk_text(content.strip())
    rows = []
    for i, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)
        rows.append({
            "source_document_id": source_doc_id,
            "chunk_text": chunk,
            "topic_tags": topic_tags,
            "content_type": source_type,
            "chunk_index": i,
            "embedding": embedding,
        })
    return rows


@router.post("/ingest-knowledge", dependencies=[Depends(authenticate)])
async def ingest_knowledge(body: IngestBody):
    if not body.title.strip() or not body.content.strip():
        raise HTTPException(status_code=400, detail="title and content are required")

    try:
        doc_res = (
            supabase.table("source_documents")
            .insert({
                "title": body.title.strip(),
                "source_type": body.sourceType,
                "source_url": body.sourceUrl.strip() if body.sourceUrl else None,
            })
            .execute()
        )
        doc_id = doc_res.data[0]["id"]
        tags = [t.strip().lower() for t in body.topicTags if t.strip()]

        rows = _build_chunk_rows(body.content, doc_id, tags, body.sourceType)
        supabase.table("knowledge_chunks").insert(rows).execute()

        logger.info('"%s" -> %d chunks stored with embeddings', body.title, len(rows))
        return {
            "sourceDocumentId": doc_id,
            "chunksCreated": len(rows),
            "totalWords": len(body.content.strip().split()),
        }
    except Exception as e:
        logger.error("Ingest error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/ingest-knowledge/{doc_id}", dependencies=[Depends(authenticate)])
async def update_knowledge(doc_id: str, body: IngestBody):
    if not body.title.strip() or not body.content.strip():
        raise HTTPException(status_code=400, detail="title and content are required")

    try:
        supabase.table("source_documents").update({
            "title": body.title.strip(),
            "source_type": body.sourceType,
            "source_url": body.sourceUrl.strip() if body.sourceUrl else None,
        }).eq("id", doc_id).execute()

        supabase.table("knowledge_chunks").delete().eq("source_document_id", doc_id).execute()

        tags = [t.strip().lower() for t in body.topicTags if t.strip()]
        rows = _build_chunk_rows(body.content, doc_id, tags, body.sourceType)
        supabase.table("knowledge_chunks").insert(rows).execute()

        logger.info('Updated "%s" -> %d chunks', body.title, len(rows))
        return {"sourceDocumentId": doc_id, "chunksCreated": len(rows)}
    except Exception as e:
        logger.error("Update error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/ingest-knowledge/{doc_id}", dependencies=[Depends(authenticate)])
async def delete_knowledge(doc_id: str):
    try:
        supabase.table("source_documents").delete().eq("id", doc_id).execute()
        logger.info("Deleted source document %s", doc_id)
        return {"success": True}
    except Exception as e:
        logger.error("Delete error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge", dependencies=[Depends(authenticate)])
async def list_knowledge():
    try:
        docs_res = (
            supabase.table("source_documents")
            .select("id, title, source_type, source_url")
            .order("ingested_at")
            .execute()
        )

        chunks_res = (
            supabase.table("knowledge_chunks")
            .select("source_document_id, chunk_text, topic_tags, chunk_index")
            .order("chunk_index")
            .execute()
        )

        chunk_map: dict[str, dict] = {}
        for c in chunks_res.data or []:
            sid = c["source_document_id"]
            if sid not in chunk_map:
                chunk_map[sid] = {
                    "count": 0,
                    "firstChunk": c["chunk_text"],
                    "topicTags": c["topic_tags"],
                    "allText": [],
                }
            chunk_map[sid]["count"] += 1
            chunk_map[sid]["allText"].append(c["chunk_text"])

        entries = []
        for doc in docs_res.data or []:
            info = chunk_map.get(doc["id"], {})
            entries.append({
                "id": doc["id"],
                "title": doc["title"],
                "sourceType": doc["source_type"],
                "sourceUrl": doc["source_url"],
                "chunkCount": info.get("count", 0),
                "topicTags": info.get("topicTags", []),
                "preview": info.get("firstChunk", ""),
                "fullContent": "\n\n".join(info.get("allText", [])),
            })

        return entries
    except Exception as e:
        logger.error("List error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
