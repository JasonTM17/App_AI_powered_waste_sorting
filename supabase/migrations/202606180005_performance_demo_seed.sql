alter table public.history
  add column if not exists seed_source text not null default 'hardware';

create index if not exists idx_history_owner_seed_ts
  on public.history(owner_username, seed_source, ts desc);

do $$
begin
  if exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'bin_stations'
       and column_name = 'active' and data_type = 'boolean'
  ) then
    execute 'create index if not exists idx_bin_stations_owner_active
               on public.bin_stations(assigned_owner_username, station_id) where active';
  else
    execute 'create index if not exists idx_bin_stations_owner_active
               on public.bin_stations(assigned_owner_username, station_id) where active = 1';
  end if;

  if exists (
    select 1 from information_schema.columns
     where table_schema = 'public' and table_name = 'bins'
       and column_name = 'active' and data_type = 'boolean'
  ) then
    execute 'create index if not exists idx_bins_station_index_active
               on public.bins(station_id, bin_index) where active';
  else
    execute 'create index if not exists idx_bins_station_index_active
               on public.bins(station_id, bin_index) where active = 1';
  end if;
end
$$;

create index if not exists idx_alerts_station_status_created
  on public.alerts(station_id, status, created_at desc);

create index if not exists idx_schedules_owner_date
  on public.collection_schedules(assigned_owner_username, scheduled_date desc);

do $$
begin
  if to_regclass('public.knowledge_entries') is not null then
    execute 'create index if not exists idx_knowledge_enabled_updated
               on public.knowledge_entries(enabled, updated_at desc)';
  end if;
end
$$;
