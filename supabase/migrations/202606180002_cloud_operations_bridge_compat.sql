-- Compatibility for Supabase projects that applied an earlier cloud-readiness draft.
alter table public.bin_stations add column if not exists device_id text not null default '';
alter table public.bin_stations add column if not exists note text not null default '';
alter table public.bin_stations add column if not exists seed_source text not null default 'local';
alter table public.bin_stations add column if not exists source text not null default 'supabase_bridge';
alter table public.bins add column if not exists fill_percent numeric(5,2) not null default 0;
alter table public.bins add column if not exists created_at timestamptz not null default now();
alter table public.alerts add column if not exists derived boolean not null default false;
alter table public.devices add column if not exists last_seen_at timestamptz;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'bins'
      and column_name = 'fullness_percent'
  ) then
    update public.bins
       set fill_percent = coalesce(fill_percent, fullness_percent, 0);
  end if;
end $$;
