alter table if exists public.history
  add column if not exists display_label text,
  add column if not exists label_status text,
  add column if not exists label_source text,
  add column if not exists label_confidence numeric(7,6),
  add column if not exists reviewed_by text,
  add column if not exists reviewed_at timestamptz,
  add column if not exists review_note text;

create index if not exists idx_history_owner_label_status
  on public.history(owner_username, label_status, ts desc);

create table if not exists public.history_label_audit (
  id bigserial primary key,
  history_id bigint not null references public.history(id) on delete cascade,
  previous_label text,
  new_label text not null,
  previous_status text,
  new_status text not null,
  reviewed_by text not null,
  reviewed_at timestamptz not null default now(),
  review_note text
);

create index if not exists idx_history_label_audit_history
  on public.history_label_audit(history_id, reviewed_at desc);

alter table public.history_label_audit enable row level security;

drop policy if exists "history_label_audit_admin_all" on public.history_label_audit;
create policy "history_label_audit_admin_all"
  on public.history_label_audit for all
  using (public.is_admin())
  with check (public.is_admin());

drop policy if exists "history_label_audit_user_own_read" on public.history_label_audit;
create policy "history_label_audit_user_own_read"
  on public.history_label_audit for select
  using (
    exists (
      select 1 from public.history h
       where h.id = history_id
         and h.owner_username = public.profile_username()
    )
  );
