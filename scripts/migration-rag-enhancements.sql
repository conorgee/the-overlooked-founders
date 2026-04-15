-- ============================================
-- MIGRATION: RAG Enhancements — Hybrid Search
-- Run in Supabase SQL Editor (or via pg client)
-- ============================================

-- 1. Add tsvector column for full-text search (generated, auto-updates)
ALTER TABLE public.knowledge_chunks
  ADD COLUMN IF NOT EXISTS search_vector tsvector
  GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED;

-- 2. GIN index for full-text search
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_fts
  ON public.knowledge_chunks USING GIN (search_vector);

-- 3. Fix match_knowledge: enforce threshold + return source_doc_id
CREATE OR REPLACE FUNCTION public.match_knowledge(
  query_embedding extensions.vector(384),
  match_count int default 5,
  match_threshold float default 0.3
)
RETURNS TABLE (
  id uuid,
  chunk_text text,
  topic_tags text[],
  source_title text,
  source_type text,
  source_doc_id uuid,
  similarity float
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    kc.id,
    kc.chunk_text,
    kc.topic_tags,
    sd.title AS source_title,
    sd.source_type AS source_type,
    kc.source_document_id AS source_doc_id,
    (1 - (kc.embedding <=> query_embedding))::float AS similarity
  FROM public.knowledge_chunks kc
  JOIN public.source_documents sd ON sd.id = kc.source_document_id
  WHERE kc.embedding IS NOT NULL
    AND (1 - (kc.embedding <=> query_embedding)) > match_threshold
  ORDER BY kc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- 4. New keyword search RPC
CREATE OR REPLACE FUNCTION public.keyword_search(
  search_query text,
  match_count int default 5
)
RETURNS TABLE (
  id uuid,
  chunk_text text,
  topic_tags text[],
  source_title text,
  source_type text,
  source_doc_id uuid,
  rank real
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    kc.id,
    kc.chunk_text,
    kc.topic_tags,
    sd.title AS source_title,
    sd.source_type AS source_type,
    kc.source_document_id AS source_doc_id,
    ts_rank(kc.search_vector, websearch_to_tsquery('english', search_query)) AS rank
  FROM public.knowledge_chunks kc
  JOIN public.source_documents sd ON sd.id = kc.source_document_id
  WHERE kc.search_vector @@ websearch_to_tsquery('english', search_query)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;
