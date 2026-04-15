-- ============================================
-- FEEDBACK LOOP — Schema Migration
-- Adds: feedback on chat messages, retrieval provenance logging, chunk quality scoring
-- Run this in Supabase SQL Editor after the base schema
-- ============================================

-- 1. Add feedback column to chat_messages
ALTER TABLE public.chat_messages
  ADD COLUMN IF NOT EXISTS feedback TEXT
  CHECK (feedback IN ('helpful', 'not_helpful'));

ALTER TABLE public.chat_messages
  ADD COLUMN IF NOT EXISTS feedback_at TIMESTAMPTZ;

-- 2. Retrieval logs — which chunks were retrieved for each assistant response
CREATE TABLE IF NOT EXISTS public.retrieval_logs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  message_id UUID REFERENCES public.chat_messages(id) ON DELETE CASCADE NOT NULL,
  chunk_id UUID REFERENCES public.knowledge_chunks(id) ON DELETE CASCADE,
  rank INTEGER NOT NULL,
  rrf_score FLOAT,
  similarity FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_logs_message
  ON public.retrieval_logs(message_id);

CREATE INDEX IF NOT EXISTS idx_retrieval_logs_chunk
  ON public.retrieval_logs(chunk_id);

-- 3. Chunk quality — aggregated feedback scores per chunk
CREATE TABLE IF NOT EXISTS public.chunk_quality (
  chunk_id UUID REFERENCES public.knowledge_chunks(id) ON DELETE CASCADE PRIMARY KEY,
  helpful_count INTEGER DEFAULT 0,
  not_helpful_count INTEGER DEFAULT 0,
  wilson_score FLOAT DEFAULT 0.0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE public.retrieval_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chunk_quality ENABLE ROW LEVEL SECURITY;

-- Retrieval logs: readable by authenticated users (admins need this for analytics)
CREATE POLICY "Authenticated users can read retrieval logs"
  ON public.retrieval_logs FOR SELECT
  USING (auth.role() = 'authenticated');

-- Chunk quality: readable by authenticated users (needed for feedback-boosted re-ranking)
CREATE POLICY "Authenticated users can read chunk quality"
  ON public.chunk_quality FOR SELECT
  USING (auth.role() = 'authenticated');

-- Users can update feedback on their own chat messages
CREATE POLICY "Users can update own message feedback"
  ON public.chat_messages FOR UPDATE
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
