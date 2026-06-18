-- Trash Sorter Pro full-cloud readiness schema.
-- Frontend reads use Supabase Auth + RLS. The local hardware bridge writes with
-- a server-side/service credential only; never expose it to the browser.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text not null unique,
  display_name text not null default '',
  role text not null check (role in ('admin', 'user')),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.devices (
  device_id text primary key,
  device_name text not null default '',
  location text not null default '',
  owner_username text not null default '',
  status text not null default 'offline',
  message text not null default '',
  active boolean not null default true,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bin_stations (
  station_id text primary key,
  name text not null,
  area text not null default '',
  address text not null default '',
  latitude double precision,
  longitude double precision,
  status text not null default 'candidate',
  coordinate_verified boolean not null default false,
  assigned_owner_username text not null default '',
  device_id text not null default '',
  note text not null default '',
  seed_source text not null default 'local',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bins (
  bin_id text primary key,
  station_id text not null references public.bin_stations(station_id) on delete cascade,
  command text not null check (command in ('O', 'R', 'I')),
  bin_index integer not null check (bin_index between 1 and 3),
  label text not null,
  fill_percent numeric(5,2) not null default 0 check (fill_percent between 0 and 100),
  status text not null default 'unknown' check (status in ('unknown', 'normal', 'warning', 'full', 'offline')),
  active boolean not null default true,
  updated_at timestamptz not null default now(),
  unique (station_id, bin_index)
);

create table if not exists public.alerts (
  alert_id text primary key,
  station_id text not null default '',
  bin_id text not null default '',
  device_id text not null default '',
  severity text not null check (severity in ('info', 'success', 'warning', 'danger')),
  title text not null,
  message text not null default '',
  status text not null default 'open' check (status in ('open', 'acknowledged', 'resolved')),
  source text not null default 'manual',
  actor_username text not null default '',
  derived boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists public.collection_schedules (
  schedule_id text primary key,
  station_id text not null references public.bin_stations(station_id) on delete cascade,
  assigned_owner_username text not null default '',
  scheduled_date date not null,
  window_start time,
  window_end time,
  status text not null default 'scheduled',
  note text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  completed_by text not null default ''
);

create table if not exists public.collection_events (
  id uuid primary key default gen_random_uuid(),
  schedule_id text not null references public.collection_schedules(schedule_id) on delete cascade,
  station_id text not null,
  completed_by text not null,
  note text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.device_issues (
  issue_id text primary key,
  station_id text not null,
  bin_id text not null default '',
  device_id text not null default '',
  issue_type text not null,
  severity text not null check (severity in ('info', 'warning', 'danger')),
  description text not null default '',
  status text not null default 'open' check (status in ('open', 'acknowledged', 'resolved')),
  reporter_username text not null default '',
  reporter_profile_id uuid references auth.users(id) on delete set null,
  alert_id text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists public.history (
  id bigserial primary key,
  local_history_id bigint,
  device_id text not null default '',
  owner_username text not null default '',
  ts timestamptz not null,
  cls_id integer not null,
  cls_name text not null,
  confidence numeric(7,6) not null default 0,
  route_label text,
  bin_index integer,
  uart_command text,
  ack_status text,
  rtt_ms integer,
  image_available boolean not null default false,
  created_at timestamptz not null default now(),
  unique (device_id, local_history_id)
);

create table if not exists public.knowledge_entries (
  id text primary key,
  title text not null,
  roles text[] not null default array['admin', 'user'],
  keywords text[] not null default array[]::text[],
  body text not null,
  enabled boolean not null default true,
  source text not null default 'local',
  updated_at timestamptz not null default now()
);

create table if not exists public.training_jobs (
  job_id text primary key,
  run_name text not null default '',
  status text not null default 'idle',
  profile text not null default '',
  class_name text not null default '',
  progress_percent numeric(5,2) not null default 0,
  metrics jsonb not null default '{}'::jsonb,
  message text not null default '',
  best_model_ref text not null default '',
  last_model_ref text not null default '',
  started_at timestamptz,
  completed_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists public.realtime_events (
  id bigserial primary key,
  event_name text not null,
  topic text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function public.profile_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select coalesce((select role from public.profiles where id = auth.uid() and active), 'anonymous');
$$;

create or replace function public.profile_username()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select coalesce((select username from public.profiles where id = auth.uid() and active), '');
$$;

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.profile_role() = 'admin';
$$;

create or replace function public.station_is_assigned(station text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.bin_stations s
    where s.station_id = station
      and s.active
      and s.assigned_owner_username = public.profile_username()
  );
$$;

create or replace function public.emit_bin_status_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'INSERT'
     or new.fill_percent is distinct from old.fill_percent
     or new.status is distinct from old.status then
    insert into public.realtime_events(event_name, topic, payload)
    values (
      'bin_status_changed',
      'project:operations',
      jsonb_build_object(
        'station_id', new.station_id,
        'bin_id', new.bin_id,
        'bin_code', new.command || '/bin' || new.bin_index,
        'fill_percent', new.fill_percent,
        'fill_status', new.status
      )
    );
  end if;
  return new;
end;
$$;

create or replace function public.emit_alert_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.realtime_events(event_name, topic, payload)
  values (
    case when new.status = 'resolved' then 'alert_resolved' else 'alert_created' end,
    'project:alerts',
    jsonb_build_object(
      'alert_id', new.alert_id,
      'severity', new.severity,
      'station_id', new.station_id,
      'bin_id', new.bin_id,
      'status', new.status
    )
  );
  return new;
end;
$$;

create or replace function public.emit_collection_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.realtime_events(event_name, topic, payload)
  values (
    'collection_completed',
    'project:operations',
    jsonb_build_object(
      'schedule_id', new.schedule_id,
      'station_id', new.station_id,
      'completed_by', new.completed_by
    )
  );
  return new;
end;
$$;

create or replace function public.emit_device_issue_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.realtime_events(event_name, topic, payload)
  values (
    'device_issue_created',
    'project:alerts',
    jsonb_build_object(
      'issue_id', new.issue_id,
      'station_id', new.station_id,
      'severity', new.severity,
      'reporter_username', new.reporter_username
    )
  );
  return new;
end;
$$;

create or replace function public.emit_device_status_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'INSERT' or new.status is distinct from old.status then
    insert into public.realtime_events(event_name, topic, payload)
    values (
      'device_status_changed',
      'project:operations',
      jsonb_build_object('device_id', new.device_id, 'status', new.status)
    );
  end if;
  return new;
end;
$$;

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at before update on public.profiles
for each row execute function public.set_updated_at();

drop trigger if exists trg_devices_updated_at on public.devices;
create trigger trg_devices_updated_at before update on public.devices
for each row execute function public.set_updated_at();

drop trigger if exists trg_bin_stations_updated_at on public.bin_stations;
create trigger trg_bin_stations_updated_at before update on public.bin_stations
for each row execute function public.set_updated_at();

drop trigger if exists trg_alerts_updated_at on public.alerts;
create trigger trg_alerts_updated_at before update on public.alerts
for each row execute function public.set_updated_at();

drop trigger if exists trg_bins_realtime on public.bins;
create trigger trg_bins_realtime after insert or update on public.bins
for each row execute function public.emit_bin_status_event();

drop trigger if exists trg_alerts_realtime on public.alerts;
create trigger trg_alerts_realtime after insert or update on public.alerts
for each row execute function public.emit_alert_event();

drop trigger if exists trg_collection_events_realtime on public.collection_events;
create trigger trg_collection_events_realtime after insert on public.collection_events
for each row execute function public.emit_collection_event();

drop trigger if exists trg_device_issues_realtime on public.device_issues;
create trigger trg_device_issues_realtime after insert on public.device_issues
for each row execute function public.emit_device_issue_event();

drop trigger if exists trg_devices_realtime on public.devices;
create trigger trg_devices_realtime after insert or update on public.devices
for each row execute function public.emit_device_status_event();

alter table public.profiles enable row level security;
alter table public.devices enable row level security;
alter table public.bin_stations enable row level security;
alter table public.bins enable row level security;
alter table public.alerts enable row level security;
alter table public.collection_schedules enable row level security;
alter table public.collection_events enable row level security;
alter table public.device_issues enable row level security;
alter table public.history enable row level security;
alter table public.knowledge_entries enable row level security;
alter table public.training_jobs enable row level security;
alter table public.realtime_events enable row level security;

create policy "profiles_admin_all" on public.profiles for all using (public.is_admin()) with check (public.is_admin());
create policy "profiles_own_read" on public.profiles for select using (id = auth.uid());

create policy "devices_admin_all" on public.devices for all using (public.is_admin()) with check (public.is_admin());
create policy "devices_user_assigned_read" on public.devices for select using (active and owner_username = public.profile_username());

create policy "stations_admin_all" on public.bin_stations for all using (public.is_admin()) with check (public.is_admin());
create policy "stations_user_assigned_read" on public.bin_stations for select using (active and assigned_owner_username = public.profile_username());

create policy "bins_admin_all" on public.bins for all using (public.is_admin()) with check (public.is_admin());
create policy "bins_user_assigned_read" on public.bins for select using (active and public.station_is_assigned(station_id));

create policy "alerts_admin_all" on public.alerts for all using (public.is_admin()) with check (public.is_admin());
create policy "alerts_user_assigned_read" on public.alerts for select using (public.station_is_assigned(station_id));

create policy "schedules_admin_all" on public.collection_schedules for all using (public.is_admin()) with check (public.is_admin());
create policy "schedules_user_assigned_read" on public.collection_schedules for select using (assigned_owner_username = public.profile_username());

create policy "events_admin_all" on public.collection_events for all using (public.is_admin()) with check (public.is_admin());
create policy "events_user_assigned_read" on public.collection_events for select using (public.station_is_assigned(station_id));
create policy "events_user_insert_assigned" on public.collection_events for insert with check (completed_by = public.profile_username() and public.station_is_assigned(station_id));

create policy "issues_admin_all" on public.device_issues for all using (public.is_admin()) with check (public.is_admin());
create policy "issues_user_assigned_read" on public.device_issues for select using (reporter_profile_id = auth.uid() or public.station_is_assigned(station_id));
create policy "issues_user_insert_assigned" on public.device_issues for insert with check (reporter_profile_id = auth.uid() and reporter_username = public.profile_username() and public.station_is_assigned(station_id));

create policy "history_admin_all" on public.history for all using (public.is_admin()) with check (public.is_admin());
create policy "history_user_own_read" on public.history for select using (owner_username = public.profile_username());

create policy "knowledge_admin_all" on public.knowledge_entries for all using (public.is_admin()) with check (public.is_admin());
create policy "knowledge_role_read" on public.knowledge_entries for select using (enabled and public.profile_role() = any(roles));

create policy "training_jobs_admin_all" on public.training_jobs for all using (public.is_admin()) with check (public.is_admin());

create policy "realtime_events_admin_read" on public.realtime_events for select using (public.is_admin());
create policy "realtime_events_user_read" on public.realtime_events for select using (
  event_name in ('bin_status_changed', 'alert_created', 'alert_resolved', 'collection_completed', 'device_issue_created', 'device_status_changed')
  and (
    not (payload ? 'station_id')
    or coalesce(payload ->> 'station_id', '') = ''
    or public.station_is_assigned(payload ->> 'station_id')
    or coalesce(payload ->> 'completed_by', '') = public.profile_username()
    or coalesce(payload ->> 'reporter_username', '') = public.profile_username()
  )
);

create index if not exists idx_bin_stations_owner on public.bin_stations(assigned_owner_username) where active;
create index if not exists idx_bins_station on public.bins(station_id);
create index if not exists idx_alerts_station_status on public.alerts(station_id, status);
create index if not exists idx_schedules_owner on public.collection_schedules(assigned_owner_username);
create index if not exists idx_history_owner_ts on public.history(owner_username, ts desc);
create index if not exists idx_realtime_events_created on public.realtime_events(created_at desc);
