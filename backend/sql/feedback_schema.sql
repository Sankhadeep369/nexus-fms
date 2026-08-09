-- NEXUS answer-feedback schema — run once in your Supabase SQL Editor.
create table if not exists feedback (
  id uuid primary key default gen_random_uuid(),
  query text not null,
  answer text,
  rating text not null check (rating in ('up', 'down')),
  mode text,
  comment text,
  created_at timestamptz not null default now()
);

alter table feedback enable row level security;

create policy "Allow all access for anon key" on feedback
  for all using (true) with check (true);
