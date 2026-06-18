create or replace function public.profile_role()
returns text language plpgsql stable security definer set search_path = public
as $$
declare
  result text := 'anonymous';
begin
  if to_regclass('public.profiles') is null then
    return result;
  end if;
  execute
    'select coalesce((select role from public.profiles
      where id::text = $1 and coalesce(active::text, ''true'') not in
      (''0'', ''false'', ''f'', ''no'')), ''anonymous'')'
    into result
    using auth.uid()::text;
  return result;
end;
$$;

create or replace function public.profile_username()
returns text language plpgsql stable security definer set search_path = public
as $$
declare
  result text := '';
begin
  if to_regclass('public.profiles') is null then
    return result;
  end if;
  execute
    'select coalesce((select username from public.profiles
      where id::text = $1 and coalesce(active::text, ''true'') not in
      (''0'', ''false'', ''f'', ''no'')), '''')'
    into result
    using auth.uid()::text;
  return result;
end;
$$;

create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = public
as $$
  select public.profile_role() = 'admin';
$$;

create or replace function public.station_is_assigned(station text)
returns boolean language sql stable security definer set search_path = public
as $$
  select exists (
    select 1 from public.bin_stations
     where station_id = station
       and coalesce(active::text, 'true') not in ('0', 'false', 'f', 'no')
       and assigned_owner_username = public.profile_username()
  );
$$;

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

create index if not exists idx_history_owner_ts
  on public.history(owner_username, ts desc);

alter table public.history enable row level security;

drop policy if exists "history_admin_all" on public.history;
create policy "history_admin_all"
  on public.history for all
  using (public.is_admin())
  with check (public.is_admin());

drop policy if exists "history_user_own_read" on public.history;
create policy "history_user_own_read"
  on public.history for select
  using (owner_username = public.profile_username());

create table if not exists public.demo_hardware_targets (
  owner_username text primary key,
  station_id text not null references public.bin_stations(station_id) on delete cascade,
  bin_id text not null default '',
  bin_index int not null check (bin_index between 1 and 3),
  selected_by text not null default '',
  selected_at timestamptz not null default now(),
  last_applied_at timestamptz,
  last_percent numeric(5,2),
  active boolean not null default true
);

create index if not exists idx_demo_hardware_targets_station
  on public.demo_hardware_targets(station_id, bin_index)
  where active;

alter table public.demo_hardware_targets enable row level security;

drop policy if exists "demo_hardware_targets_admin_all" on public.demo_hardware_targets;
create policy "demo_hardware_targets_admin_all"
  on public.demo_hardware_targets
  for all
  using (public.is_admin())
  with check (public.is_admin());

drop policy if exists "demo_hardware_targets_user_own" on public.demo_hardware_targets;
create policy "demo_hardware_targets_user_own"
  on public.demo_hardware_targets
  for all
  using (
    owner_username = public.profile_username()
    and public.station_is_assigned(station_id)
  )
  with check (
    owner_username = public.profile_username()
    and public.station_is_assigned(station_id)
  );
