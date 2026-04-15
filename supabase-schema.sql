-- ============================================
-- THE STEVEN FOUNDATION — Database Schema
-- Run this in Supabase SQL Editor
-- ============================================

-- 1. PROFILES (extends Supabase auth.users)
create table public.profiles (
  id uuid references auth.users on delete cascade primary key,
  email text not null,
  full_name text,
  role text not null default 'applicant' check (role in ('applicant', 'participant', 'admin')),
  linkedin_url text,
  cohort_id uuid,
  created_at timestamptz default now()
);

-- 2. COHORTS
create table public.cohorts (
  id uuid default gen_random_uuid() primary key,
  name text not null,
  start_date date,
  end_date date,
  max_participants int default 25,
  created_at timestamptz default now()
);

-- Add foreign key for profiles.cohort_id
alter table public.profiles
  add constraint profiles_cohort_id_fkey
  foreign key (cohort_id) references public.cohorts(id);

-- 3. APPLICATIONS
create table public.applications (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade,
  first_name text not null,
  last_name text not null,
  email text not null,
  business_name text,
  business_idea text,
  stage text check (stage in ('idea', 'mvp', 'launched', 'growing')),
  video_pitch_url text,
  ai_score int,
  ai_summary text,
  status text default 'pending' check (status in ('pending', 'under_review', 'accepted', 'rejected')),
  reviewed_at timestamptz,
  created_at timestamptz default now()
);

-- 4. WEEKLY SUBMISSIONS
create table public.weekly_submissions (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  cohort_id uuid references public.cohorts(id),
  week_number int not null check (week_number between 1 and 8),
  video_url text,
  transcript text,
  extracted_topics jsonb,
  extracted_questions jsonb,
  status text default 'submitted' check (status in ('submitted', 'processing', 'responded')),
  created_at timestamptz default now()
);

-- 5. AI RESPONSES
create table public.ai_responses (
  id uuid default gen_random_uuid() primary key,
  submission_id uuid references public.weekly_submissions(id) on delete cascade not null,
  response_text text not null,
  audio_url text,
  video_url text,
  sources_cited jsonb,
  feedback_rating int check (feedback_rating between 1 and 5),
  generated_at timestamptz default now()
);

-- 6. SOURCE DOCUMENTS
create table public.source_documents (
  id uuid default gen_random_uuid() primary key,
  title text not null,
  source_type text check (source_type in ('podcast', 'article', 'tweet', 'linkedin', 'book', 'interview')),
  source_url text,
  original_date date,
  raw_content_url text,
  ingested_at timestamptz default now()
);

-- 7. KNOWLEDGE CHUNKS
create table public.knowledge_chunks (
  id uuid default gen_random_uuid() primary key,
  source_document_id uuid references public.source_documents(id) on delete cascade,
  chunk_text text not null,
  topic_tags text[],
  content_type text,
  chunk_index int,
  created_at timestamptz default now()
);

-- 8. CHAT MESSAGES
create table public.chat_messages (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  sources_cited jsonb,
  created_at timestamptz default now()
);

-- ============================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================

-- Profiles: users can read/update their own profile, admins can read all
alter table public.profiles enable row level security;

create policy "Users can view own profile"
  on public.profiles for select
  using (auth.uid() = id);

create policy "Users can update own profile"
  on public.profiles for update
  using (auth.uid() = id);

create policy "Admins can view all profiles"
  on public.profiles for select
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and role = 'admin'
    )
  );

-- Applications: users see own, admins see all
alter table public.applications enable row level security;

create policy "Users can view own applications"
  on public.applications for select
  using (user_id = auth.uid());

create policy "Users can insert own applications"
  on public.applications for insert
  with check (true);

create policy "Admins can view all applications"
  on public.applications for select
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and role = 'admin'
    )
  );

create policy "Admins can update applications"
  on public.applications for update
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and role = 'admin'
    )
  );

-- Weekly submissions: users see own
alter table public.weekly_submissions enable row level security;

create policy "Users can view own submissions"
  on public.weekly_submissions for select
  using (user_id = auth.uid());

create policy "Users can insert own submissions"
  on public.weekly_submissions for insert
  with check (user_id = auth.uid());

-- AI responses: users see responses to their submissions
alter table public.ai_responses enable row level security;

create policy "Users can view own responses"
  on public.ai_responses for select
  using (
    exists (
      select 1 from public.weekly_submissions
      where weekly_submissions.id = ai_responses.submission_id
      and weekly_submissions.user_id = auth.uid()
    )
  );

create policy "Users can rate responses"
  on public.ai_responses for update
  using (
    exists (
      select 1 from public.weekly_submissions
      where weekly_submissions.id = ai_responses.submission_id
      and weekly_submissions.user_id = auth.uid()
    )
  );

-- Chat messages: users see own
alter table public.chat_messages enable row level security;

create policy "Users can view own messages"
  on public.chat_messages for select
  using (user_id = auth.uid());

create policy "Users can insert own messages"
  on public.chat_messages for insert
  with check (user_id = auth.uid());

-- Knowledge chunks & source docs: readable by all authenticated users
alter table public.knowledge_chunks enable row level security;
alter table public.source_documents enable row level security;

create policy "Authenticated users can read knowledge"
  on public.knowledge_chunks for select
  using (auth.role() = 'authenticated');

create policy "Authenticated users can read sources"
  on public.source_documents for select
  using (auth.role() = 'authenticated');

-- Cohorts: readable by all authenticated users
alter table public.cohorts enable row level security;

create policy "Authenticated users can read cohorts"
  on public.cohorts for select
  using (auth.role() = 'authenticated');

-- ============================================
-- AUTO-CREATE PROFILE ON SIGNUP
-- ============================================

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email, full_name)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', '')
  );
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================
-- SEED: Create first cohort
-- ============================================

insert into public.cohorts (name, start_date, end_date, max_participants)
values ('Cohort 1 — Pilot', '2026-07-01', '2026-08-26', 25);

-- ============================================
-- VECTOR EMBEDDINGS (pgvector) for semantic RAG
-- ============================================

-- Enable pgvector extension
create extension if not exists vector with schema extensions;

-- Add embedding column to knowledge_chunks
alter table public.knowledge_chunks
  add column if not exists embedding extensions.vector(384);

-- HNSW index for cosine similarity search
create index if not exists knowledge_chunks_embedding_idx
  on public.knowledge_chunks
  using hnsw (embedding extensions.vector_cosine_ops);

-- RPC function for similarity search
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
  source_doc_id uuid,
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
    kc.source_document_id as source_doc_id,
    (1 - (kc.embedding <=> query_embedding))::float as similarity
  from public.knowledge_chunks kc
  join public.source_documents sd on sd.id = kc.source_document_id
  where kc.embedding is not null
    and (1 - (kc.embedding <=> query_embedding)) > match_threshold
  order by kc.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Keyword search RPC (for hybrid search)
alter table public.knowledge_chunks
  add column if not exists search_vector tsvector
  generated always as (to_tsvector('english', chunk_text)) stored;

create index if not exists idx_knowledge_chunks_fts
  on public.knowledge_chunks using gin (search_vector);

create or replace function public.keyword_search(
  search_query text,
  match_count int default 5
)
returns table (
  id uuid,
  chunk_text text,
  topic_tags text[],
  source_title text,
  source_type text,
  source_doc_id uuid,
  rank real
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
    kc.source_document_id as source_doc_id,
    ts_rank(kc.search_vector, websearch_to_tsquery('english', search_query)) as rank
  from public.knowledge_chunks kc
  join public.source_documents sd on sd.id = kc.source_document_id
  where kc.search_vector @@ websearch_to_tsquery('english', search_query)
  order by rank desc
  limit match_count;
end;
$$;
