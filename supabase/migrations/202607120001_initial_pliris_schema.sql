-- Pliris BA Bot: hosted Supabase foundation
-- Run against the hosted Supabase project through the SQL Editor
-- or with the Supabase CLI after linking the repository.
--
-- Embedding model baseline:
--   OpenAI text-embedding-3-small
--   1536 dimensions
--
-- Security baseline:
--   No browser or anonymous access to the knowledge base.
--   The FastAPI backend and ingestion pipeline use the server-side secret key.
--   Never expose the secret key in Streamlit/browser code.

begin;

create schema if not exists extensions;

create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;

-- ---------------------------------------------------------------------------
-- Shared updated_at trigger
-- ---------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Knowledge-base source documents
-- ---------------------------------------------------------------------------

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  source_filename text not null,
  storage_bucket text not null default 'knowledge-base',
  storage_path text,
  author text,
  edition text,
  publication_year smallint,
  mime_type text not null default 'application/pdf',
  checksum_sha256 text not null,
  page_count integer check (page_count is null or page_count > 0),
  status text not null default 'pending'
    check (status in ('pending', 'processing', 'ready', 'failed', 'archived')),
  ingestion_error text,
  metadata jsonb not null default '{}'::jsonb,
  last_ingested_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (checksum_sha256)
);

create index if not exists documents_status_idx
  on public.documents (status);

create index if not exists documents_title_idx
  on public.documents (lower(title));

drop trigger if exists documents_set_updated_at on public.documents;
create trigger documents_set_updated_at
before update on public.documents
for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Page-aware document chunks
-- ---------------------------------------------------------------------------

create table if not exists public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null
    references public.documents(id) on delete cascade,
  chunk_index integer not null check (chunk_index >= 0),
  content text not null check (length(btrim(content)) > 0),
  page_start integer check (page_start is null or page_start > 0),
  page_end integer check (
    page_end is null
    or page_end > 0
    and (page_start is null or page_end >= page_start)
  ),
  chapter text,
  section text,
  heading_path text[] not null default '{}'::text[],
  token_count integer check (token_count is null or token_count > 0),
  content_hash text not null,
  embedding extensions.vector(1536),
  embedding_model text not null default 'text-embedding-3-small',
  embedding_dimensions integer not null default 1536
    check (embedding_dimensions = 1536),
  metadata jsonb not null default '{}'::jsonb,
  -- Maintained by a trigger rather than a generated expression.
  -- array_to_string(text[], text) is not immutable, so PostgreSQL does not
  -- allow it inside a stored generated column.
  fts tsvector not null default ''::tsvector,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (document_id, chunk_index),
  unique (document_id, content_hash)
);

create index if not exists document_chunks_document_idx
  on public.document_chunks (document_id, chunk_index);

create index if not exists document_chunks_fts_idx
  on public.document_chunks using gin (fts);

-- Keep the full-text vector synchronized without relying on a generated column.
create or replace function public.set_document_chunk_fts()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_catalog
as $$
begin
  new.fts := to_tsvector(
    'pg_catalog.english'::regconfig,
    coalesce(new.chapter, '') || ' ' ||
    coalesce(new.section, '') || ' ' ||
    coalesce(array_to_string(new.heading_path, ' '), '') || ' ' ||
    coalesce(new.content, '')
  );
  return new;
end;
$$;

drop trigger if exists document_chunks_set_fts on public.document_chunks;
create trigger document_chunks_set_fts
before insert or update of content, chapter, section, heading_path
on public.document_chunks
for each row execute function public.set_document_chunk_fts();

-- HNSW can be created before data is loaded and performs well as the corpus grows.
create index if not exists document_chunks_embedding_hnsw_idx
  on public.document_chunks
  using hnsw (embedding vector_cosine_ops);

drop trigger if exists document_chunks_set_updated_at on public.document_chunks;
create trigger document_chunks_set_updated_at
before update on public.document_chunks
for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Ingestion audit
-- ---------------------------------------------------------------------------

create table if not exists public.ingestion_runs (
  id uuid primary key default gen_random_uuid(),
  status text not null default 'running'
    check (status in ('running', 'completed', 'completed_with_errors', 'failed')),
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  documents_discovered integer not null default 0 check (documents_discovered >= 0),
  documents_processed integer not null default 0 check (documents_processed >= 0),
  chunks_created integer not null default 0 check (chunks_created >= 0),
  chunks_embedded integer not null default 0 check (chunks_embedded >= 0),
  error_count integer not null default 0 check (error_count >= 0),
  errors jsonb not null default '[]'::jsonb,
  configuration jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Conversation, answer, feedback, and monitoring records
-- ---------------------------------------------------------------------------

create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  client_session_id text,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists conversations_set_updated_at on public.conversations;
create trigger conversations_set_updated_at
before update on public.conversations
for each row execute function public.set_updated_at();

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null
    references public.conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  scope_status text check (
    scope_status is null
    or scope_status in ('in_scope', 'borderline', 'out_of_scope')
  ),
  scope_confidence double precision check (
    scope_confidence is null
    or scope_confidence between 0 and 1
  ),
  citations jsonb not null default '[]'::jsonb,
  model_name text,
  input_tokens integer check (input_tokens is null or input_tokens >= 0),
  output_tokens integer check (output_tokens is null or output_tokens >= 0),
  latency_ms integer check (latency_ms is null or latency_ms >= 0),
  created_at timestamptz not null default now()
);

create index if not exists messages_conversation_created_idx
  on public.messages (conversation_id, created_at);

create table if not exists public.retrieval_queries (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references public.conversations(id) on delete set null,
  user_message_id uuid references public.messages(id) on delete set null,
  original_query text not null,
  rewritten_query text,
  scope_status text not null
    check (scope_status in ('in_scope', 'borderline', 'out_of_scope')),
  scope_confidence double precision not null
    check (scope_confidence between 0 and 1),
  retrieval_method text,
  requested_match_count integer check (
    requested_match_count is null or requested_match_count > 0
  ),
  latency_ms integer check (latency_ms is null or latency_ms >= 0),
  created_at timestamptz not null default now()
);

create table if not exists public.retrieval_results (
  id uuid primary key default gen_random_uuid(),
  retrieval_query_id uuid not null
    references public.retrieval_queries(id) on delete cascade,
  chunk_id uuid not null
    references public.document_chunks(id) on delete cascade,
  result_rank integer not null check (result_rank > 0),
  hybrid_score double precision,
  semantic_rank integer check (semantic_rank is null or semantic_rank > 0),
  keyword_rank integer check (keyword_rank is null or keyword_rank > 0),
  reranker_score double precision,
  selected_for_context boolean not null default false,
  created_at timestamptz not null default now(),
  unique (retrieval_query_id, result_rank)
);

create index if not exists retrieval_results_query_idx
  on public.retrieval_results (retrieval_query_id, result_rank);

create table if not exists public.user_feedback (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references public.conversations(id) on delete set null,
  assistant_message_id uuid not null
    references public.messages(id) on delete cascade,
  rating smallint not null check (rating in (-1, 1)),
  citation_helpful boolean,
  scope_decision_correct boolean,
  comment text,
  created_at timestamptz not null default now(),
  unique (assistant_message_id)
);

create table if not exists public.monitoring_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null,
  conversation_id uuid references public.conversations(id) on delete set null,
  message_id uuid references public.messages(id) on delete set null,
  severity text not null default 'info'
    check (severity in ('debug', 'info', 'warning', 'error', 'critical')),
  properties jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists monitoring_events_type_created_idx
  on public.monitoring_events (event_type, created_at desc);

-- ---------------------------------------------------------------------------
-- Hybrid retrieval RPC: full-text + semantic retrieval with RRF
-- ---------------------------------------------------------------------------

create or replace function public.hybrid_search(
  query_text text,
  query_embedding extensions.vector(1536),
  match_count integer default 8,
  full_text_weight double precision default 1.0,
  semantic_weight double precision default 1.0,
  rrf_k integer default 50,
  filter_document_ids uuid[] default null
)
returns table (
  chunk_id uuid,
  document_id uuid,
  document_title text,
  content text,
  page_start integer,
  page_end integer,
  chapter text,
  section text,
  metadata jsonb,
  score double precision,
  semantic_rank bigint,
  keyword_rank bigint
)
language sql
stable
security invoker
set search_path = public, extensions
as $$
  with full_text as (
    select
      dc.id,
      row_number() over (
        order by ts_rank_cd(
          dc.fts,
          websearch_to_tsquery('english'::regconfig, query_text)
        ) desc
      ) as rank_ix
    from public.document_chunks dc
    join public.documents d on d.id = dc.document_id
    where d.status = 'ready'
      and dc.fts @@ websearch_to_tsquery('english'::regconfig, query_text)
      and (
        filter_document_ids is null
        or dc.document_id = any(filter_document_ids)
      )
    order by ts_rank_cd(
      dc.fts,
      websearch_to_tsquery('english'::regconfig, query_text)
    ) desc
    limit least(greatest(match_count * 4, match_count), 100)
  ),
  semantic as (
    select
      dc.id,
      row_number() over (
        order by dc.embedding <=> query_embedding
      ) as rank_ix
    from public.document_chunks dc
    join public.documents d on d.id = dc.document_id
    where d.status = 'ready'
      and dc.embedding is not null
      and (
        filter_document_ids is null
        or dc.document_id = any(filter_document_ids)
      )
    order by dc.embedding <=> query_embedding
    limit least(greatest(match_count * 4, match_count), 100)
  ),
  candidates as (
    select id from full_text
    union
    select id from semantic
  )
  select
    dc.id as chunk_id,
    dc.document_id,
    d.title as document_title,
    dc.content,
    dc.page_start,
    dc.page_end,
    dc.chapter,
    dc.section,
    dc.metadata,
    (
      coalesce(full_text_weight / (rrf_k + ft.rank_ix), 0.0) +
      coalesce(semantic_weight / (rrf_k + sem.rank_ix), 0.0)
    )::double precision as score,
    sem.rank_ix as semantic_rank,
    ft.rank_ix as keyword_rank
  from candidates c
  join public.document_chunks dc on dc.id = c.id
  join public.documents d on d.id = dc.document_id
  left join full_text ft on ft.id = c.id
  left join semantic sem on sem.id = c.id
  order by score desc
  limit greatest(match_count, 1);
$$;

-- ---------------------------------------------------------------------------
-- Private Storage bucket for copyrighted/local knowledge-base PDFs
-- ---------------------------------------------------------------------------

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'knowledge-base',
  'knowledge-base',
  false,
  104857600,
  array['application/pdf']
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- ---------------------------------------------------------------------------
-- Security: server-side only for the first release
-- ---------------------------------------------------------------------------

alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;
alter table public.ingestion_runs enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.retrieval_queries enable row level security;
alter table public.retrieval_results enable row level security;
alter table public.user_feedback enable row level security;
alter table public.monitoring_events enable row level security;

-- Remove Data API access from browser-facing roles.
revoke all on table public.documents from anon, authenticated;
revoke all on table public.document_chunks from anon, authenticated;
revoke all on table public.ingestion_runs from anon, authenticated;
revoke all on table public.conversations from anon, authenticated;
revoke all on table public.messages from anon, authenticated;
revoke all on table public.retrieval_queries from anon, authenticated;
revoke all on table public.retrieval_results from anon, authenticated;
revoke all on table public.user_feedback from anon, authenticated;
revoke all on table public.monitoring_events from anon, authenticated;

revoke execute on function public.hybrid_search(
  text,
  extensions.vector,
  integer,
  double precision,
  double precision,
  integer,
  uuid[]
) from public, anon, authenticated;

-- The backend secret key maps to service_role and bypasses RLS.
grant all on table public.documents to service_role;
grant all on table public.document_chunks to service_role;
grant all on table public.ingestion_runs to service_role;
grant all on table public.conversations to service_role;
grant all on table public.messages to service_role;
grant all on table public.retrieval_queries to service_role;
grant all on table public.retrieval_results to service_role;
grant all on table public.user_feedback to service_role;
grant all on table public.monitoring_events to service_role;

grant execute on function public.hybrid_search(
  text,
  extensions.vector,
  integer,
  double precision,
  double precision,
  integer,
  uuid[]
) to service_role;

commit;
