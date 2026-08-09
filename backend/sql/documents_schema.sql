-- NEXUS self-serve document ingestion — run once in your Supabase SQL Editor.
-- Uploaded docs are chunked, enriched, embedded, and stored here so they survive
-- HF Space restarts. Embeddings are kept as a JSON float array (search stays
-- in-memory, so no pgvector extension is required).

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  owner text not null default 'global',   -- local-profile email, or 'global'
  filename text not null,
  title text,
  summary text,
  category text,
  num_chunks int not null default 0,
  status text not null default 'ready',    -- ready | failed
  created_at timestamptz not null default now()
);

create table if not exists document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  owner text not null default 'global',
  source_doc text not null,                -- e.g. user_docs/<owner>/<filename>#3
  section text,
  text text not null,
  embedding jsonb not null,                -- 384-float array (bge-small-en)
  created_at timestamptz not null default now()
);

create index if not exists idx_doc_chunks_owner on document_chunks (owner);
create index if not exists idx_documents_owner on documents (owner);

alter table documents enable row level security;
alter table document_chunks enable row level security;
create policy "Allow all access for anon key" on documents for all using (true) with check (true);
create policy "Allow all access for anon key" on document_chunks for all using (true) with check (true);
