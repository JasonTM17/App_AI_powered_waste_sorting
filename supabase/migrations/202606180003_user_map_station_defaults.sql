-- Give every User account a real assigned map footprint.
-- Runtime API also tops users up to three stations, so this migration is safe
-- if it is applied before or after the first production login.

create or replace function public.ensure_user_map_stations_if_available(target_username text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  clean_username text := btrim(coalesce(target_username, ''));
  existing_count integer := 0;
  station_index integer := 0;
  station_id_value text := '';
  user_hash text := '';
  base_lat double precision := 10.8020001;
  base_lng double precision := 106.7406138;
  station_name text := '';
  station_area text := '';
  station_address text := '';
begin
  if clean_username = '' then
    return;
  end if;

  select count(*)::integer
    into existing_count
    from public.bin_stations
   where assigned_owner_username = clean_username
     and coalesce(active::text, '') not in ('0', 'false', 'f', 'no', '');

  if existing_count >= 3 then
    return;
  end if;

  user_hash := substr(md5(clean_username), 1, 12);

  for station_index in 1..3 loop
    exit when existing_count >= 3;
    station_id_value := 'user-' || user_hash || '-' || station_index::text;
    if exists (select 1 from public.bin_stations where station_id = station_id_value) then
      continue;
    end if;
    base_lat := case station_index
      when 1 then 10.8020001
      when 2 then 10.8276722
      else 10.8502385
    end + ((get_byte(decode(user_hash, 'hex'), 0) % 9) - 4) * 0.00025;
    base_lng := case station_index
      when 1 then 106.7406138
      when 2 then 106.7215390
      else 106.7541974
    end + ((get_byte(decode(user_hash, 'hex'), 1) % 9) - 4) * 0.00025;
    station_name := case station_index
      when 1 then 'Diem rac khu dan cu 1'
      when 2 then 'Diem rac gan truong hoc 2'
      else 'Diem rac tuyen chinh 3'
    end;
    station_area := case station_index
      when 1 then 'Khu dan cu'
      when 2 then 'Truong hoc'
      else 'Tuyen chinh'
    end;
    station_address := 'Diem thu gom EcoSort ' || station_index::text;

    insert into public.bin_stations
      (station_id, name, area, address, latitude, longitude, status, coordinate_verified,
       assigned_owner_username, device_id, note, seed_source, active, created_at, updated_at)
    values
      (station_id_value, station_name, station_area, station_address, base_lat, base_lng,
       'active', true, clean_username, 'cloud-user-' || user_hash,
       'Auto-created map station for User account.', 'user_cloud_seed', true, now(), now())
    on conflict (station_id) do update set
      assigned_owner_username = case
        when public.bin_stations.assigned_owner_username = '' then excluded.assigned_owner_username
        else public.bin_stations.assigned_owner_username
      end,
      active = true,
      updated_at = now();

    insert into public.bins
      (bin_id, station_id, command, bin_index, label, fill_percent, status, active, created_at, updated_at)
    values
      (station_id_value || '-O', station_id_value, 'O', 1, 'Huu co', 0, 'normal', true, now(), now()),
      (station_id_value || '-R', station_id_value, 'R', 2, 'Vo co', 0, 'normal', true, now(), now()),
      (station_id_value || '-I', station_id_value, 'I', 3, 'Tai che', 0, 'normal', true, now(), now())
    on conflict (bin_id) do nothing;

    existing_count := existing_count + 1;
  end loop;
end $$;

do $$
declare
  user_record record;
begin
  if to_regclass('public.profiles') is not null then
    for user_record in
      select username
        from public.profiles
       where role = 'user'
         and active = true
         and coalesce(username, '') <> ''
    loop
      perform public.ensure_user_map_stations_if_available(user_record.username);
    end loop;
  end if;

  if to_regclass('public.accounts') is not null then
    for user_record in execute
      'select username from public.accounts where role = ''user'' and coalesce(is_active::text, ''true'') not in (''0'', ''false'', ''f'', ''no'') and coalesce(username, '''') <> '''''
    loop
      perform public.ensure_user_map_stations_if_available(user_record.username);
    end loop;
  end if;
end $$;
