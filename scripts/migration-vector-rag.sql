-- ============================================
-- MIGRATION: Vector-Embedding RAG
-- Run in Supabase SQL Editor
-- ============================================

-- 1. Enable pgvector extension
create extension if not exists vector with schema extensions;

-- 2. Add embedding column to knowledge_chunks
alter table public.knowledge_chunks
  add column if not exists embedding extensions.vector(384);

-- 3. HNSW index for cosine similarity search
create index if not exists knowledge_chunks_embedding_idx
  on public.knowledge_chunks
  using hnsw (embedding extensions.vector_cosine_ops);

-- 4. RPC function for similarity search
create or replace function public.match_knowledge(
  query_embedding extensions.vector(384),
  match_count int default 5,
  match_threshold float default 0.3
)
returns table (
  id uuid,
  chunk_text text,
  topic_tags text[],
  source_title text,
  source_type text,
  similarity float
)
language plpgsql as $$
begin
  return query
  select
    kc.id,
    kc.chunk_text,
    kc.topic_tags,
    sd.title as source_title,
    sd.source_type as source_type,
    1 - (kc.embedding <=> query_embedding) as similarity
  from public.knowledge_chunks kc
  join public.source_documents sd on sd.id = kc.source_document_id
  where kc.embedding is not null
  order by kc.embedding <=> query_embedding
  limit match_count;
end;
$$;
