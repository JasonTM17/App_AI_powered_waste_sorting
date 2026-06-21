-- Realtime event compatibility for the existing server-session production schema.
-- The Next.js server reads this narrow event log with a scoped owner query.

create table if not exists public.realtime_events (
  id bigserial primary key,
  event_name text not null,
  topic text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_realtime_events_created
  on public.realtime_events(created_at desc);

alter table public.realtime_events enable row level security;

drop policy if exists "realtime_events_service_read" on public.realtime_events;
create policy "realtime_events_service_read"
  on public.realtime_events for select
  to service_role
  using (true);

create or replace function public.emit_bin_status_event_compat()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  new_row jsonb := to_jsonb(new);
  old_row jsonb := case when tg_op = 'UPDATE' then to_jsonb(old) else '{}'::jsonb end;
  fill_value numeric := coalesce(
    nullif(new_row ->> 'fill_percent', '')::numeric,
    nullif(new_row ->> 'fullness_percent', '')::numeric,
    0
  );
begin
  if tg_op = 'INSERT'
     or fill_value is distinct from coalesce(
       nullif(old_row ->> 'fill_percent', '')::numeric,
       nullif(old_row ->> 'fullness_percent', '')::numeric,
       0
     )
     or (new_row ->> 'status') is distinct from (old_row ->> 'status') then
    insert into public.realtime_events(event_name, topic, payload)
    values (
      'bin_status_changed',
      'project:operations',
      jsonb_build_object(
        'station_id', coalesce(new_row ->> 'station_id', ''),
        'bin_id', coalesce(new_row ->> 'bin_id', ''),
        'bin_code', coalesce(new_row ->> 'command', '') || '/bin' || coalesce(new_row ->> 'bin_index', ''),
        'fill_percent', fill_value,
        'fill_status', coalesce(new_row ->> 'status', 'unknown')
      )
    );
  end if;
  return new;
end;
$$;

create or replace function public.emit_alert_event_compat()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  new_row jsonb := to_jsonb(new);
  old_row jsonb := case when tg_op = 'UPDATE' then to_jsonb(old) else '{}'::jsonb end;
begin
  if tg_op = 'INSERT' or (new_row ->> 'status') is distinct from (old_row ->> 'status') then
    insert into public.realtime_events(event_name, topic, payload)
    values (
      case when new_row ->> 'status' = 'resolved' then 'alert_resolved' else 'alert_created' end,
      'project:alerts',
      jsonb_build_object(
        'alert_id', coalesce(new_row ->> 'alert_id', ''),
        'severity', coalesce(new_row ->> 'severity', ''),
        'station_id', coalesce(new_row ->> 'station_id', ''),
        'bin_id', coalesce(new_row ->> 'bin_id', ''),
        'status', coalesce(new_row ->> 'status', '')
      )
    );
  end if;
  return new;
end;
$$;

create or replace function public.emit_collection_event_compat()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  new_row jsonb := to_jsonb(new);
begin
  insert into public.realtime_events(event_name, topic, payload)
  values (
    'collection_completed',
    'project:operations',
    jsonb_build_object(
      'schedule_id', coalesce(new_row ->> 'schedule_id', ''),
      'station_id', coalesce(new_row ->> 'station_id', ''),
      'completed_by', coalesce(new_row ->> 'completed_by', new_row ->> 'actor_username', '')
    )
  );
  return new;
end;
$$;

create or replace function public.emit_device_issue_event_compat()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  new_row jsonb := to_jsonb(new);
begin
  insert into public.realtime_events(event_name, topic, payload)
  values (
    'device_issue_created',
    'project:alerts',
    jsonb_build_object(
      'issue_id', coalesce(new_row ->> 'issue_id', ''),
      'station_id', coalesce(new_row ->> 'station_id', ''),
      'severity', coalesce(new_row ->> 'severity', ''),
      'reporter_username', coalesce(new_row ->> 'reporter_username', '')
    )
  );
  return new;
end;
$$;

create or replace function public.emit_device_status_event_compat()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  new_row jsonb := to_jsonb(new);
  old_row jsonb := case when tg_op = 'UPDATE' then to_jsonb(old) else '{}'::jsonb end;
begin
  if tg_op = 'INSERT' or (new_row ->> 'status') is distinct from (old_row ->> 'status') then
    insert into public.realtime_events(event_name, topic, payload)
    values (
      'device_status_changed',
      'project:operations',
      jsonb_build_object(
        'device_id', coalesce(new_row ->> 'device_id', ''),
        'status', coalesce(new_row ->> 'status', '')
      )
    );
  end if;
  return new;
end;
$$;

drop trigger if exists trg_bins_realtime on public.bins;
create trigger trg_bins_realtime after insert or update on public.bins
for each row execute function public.emit_bin_status_event_compat();

drop trigger if exists trg_alerts_realtime on public.alerts;
create trigger trg_alerts_realtime after insert or update on public.alerts
for each row execute function public.emit_alert_event_compat();

drop trigger if exists trg_collection_events_realtime on public.collection_events;
create trigger trg_collection_events_realtime after insert on public.collection_events
for each row execute function public.emit_collection_event_compat();

drop trigger if exists trg_device_issues_realtime on public.device_issues;
create trigger trg_device_issues_realtime after insert on public.device_issues
for each row execute function public.emit_device_issue_event_compat();

drop trigger if exists trg_devices_realtime on public.devices;
create trigger trg_devices_realtime after insert or update on public.devices
for each row execute function public.emit_device_status_event_compat();

do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime')
     and not exists (
       select 1
         from pg_publication_tables
        where pubname = 'supabase_realtime'
          and schemaname = 'public'
          and tablename = 'realtime_events'
     ) then
    alter publication supabase_realtime add table public.realtime_events;
  end if;
end;
$$;
