-- Public, payload-free Realtime pulse for custom app sessions.
-- The browser receives only a change signal, then reloads scoped data through
-- authenticated Next.js routes. Operational payloads stay service-role only.

create table if not exists public.realtime_pulse (
  id bigserial primary key,
  created_at timestamptz not null default now()
);

alter table public.realtime_pulse enable row level security;

drop policy if exists "realtime_pulse_public_read" on public.realtime_pulse;
create policy "realtime_pulse_public_read"
  on public.realtime_pulse for select
  to anon, authenticated
  using (true);

grant select on public.realtime_pulse to anon, authenticated;

create or replace function public.emit_realtime_pulse()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.realtime_pulse default values;
  return new;
end;
$$;

drop trigger if exists trg_realtime_event_pulse on public.realtime_events;
create trigger trg_realtime_event_pulse
after insert on public.realtime_events
for each row execute function public.emit_realtime_pulse();

do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime')
     and not exists (
       select 1
         from pg_publication_tables
        where pubname = 'supabase_realtime'
          and schemaname = 'public'
          and tablename = 'realtime_pulse'
     ) then
    alter publication supabase_realtime add table public.realtime_pulse;
  end if;
end;
$$;
