begin;

create table if not exists public.source_admin_events (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null
    references public.documents(id) on delete restrict,
  action text not null check (action in ('archive', 'restore')),
  actor text not null check (length(btrim(actor)) between 1 and 100),
  reason text not null check (length(btrim(reason)) between 10 and 500),
  previous_status text not null,
  new_status text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  check (
    (
      action = 'archive'
      and previous_status = 'ready'
      and new_status = 'archived'
    )
    or
    (
      action = 'restore'
      and previous_status = 'archived'
      and new_status = 'ready'
    )
  )
);

create index if not exists source_admin_events_document_created_idx
  on public.source_admin_events (document_id, created_at desc);

create or replace function public.reject_source_admin_event_mutation()
returns trigger
language plpgsql
security invoker
set search_path = public, pg_catalog
as $$
begin
  raise exception 'source_admin_events are append-only'
    using errcode = '55000';
end;
$$;

drop trigger if exists source_admin_events_append_only
  on public.source_admin_events;

create trigger source_admin_events_append_only
before update or delete
on public.source_admin_events
for each row execute function public.reject_source_admin_event_mutation();

alter table public.source_admin_events enable row level security;

revoke all on table public.source_admin_events from anon, authenticated;
grant select, insert on table public.source_admin_events to service_role;

commit;
