-- NEXUS Reminder Agent — Supabase schema
-- Run this once in your Supabase project's SQL Editor (Project → SQL Editor → New query).

create table if not exists reminders (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  notes text,
  due_date date not null,
  recipient_email text not null,
  related_vendor text,
  status text not null default 'pending' check (status in ('pending', 'sent', 'cancelled')),
  created_at timestamptz not null default now(),
  sent_at timestamptz
);

-- Speeds up the daily cron check ("find pending reminders due today or earlier")
create index if not exists idx_reminders_status_due on reminders (status, due_date);

-- Row Level Security: this is a single-tenant POC accessed only via the backend's
-- anon key over a server-to-server connection, so a permissive policy is fine here.
-- Tighten this (e.g. per-user auth) before any multi-tenant production use.
alter table reminders enable row level security;

create policy "Allow all access for anon key" on reminders
  for all
  using (true)
  with check (true);
