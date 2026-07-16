begin;

alter table public.documents
  add column if not exists manifest_id text;

create unique index if not exists documents_manifest_id_unique_idx
  on public.documents (manifest_id)
  where manifest_id is not null;

create index if not exists documents_manifest_id_lookup_idx
  on public.documents (manifest_id);

revoke all on table public.documents from anon, authenticated;
grant all on table public.documents to service_role;

commit;
