-- Cloud Eco-Share and private avatar metadata. APIs remain server-authenticated.
create extension if not exists pgcrypto;

alter table if exists public.accounts
  add column if not exists avatar_path text not null default '';

create table if not exists public.community_posts (
  post_id uuid primary key default gen_random_uuid(),
  author_account_id integer references public.accounts(id) on delete cascade,
  author_name text not null default '',
  body text not null check (char_length(body) between 1 and 500),
  tag text not null check (tag in ('Thử thách tuần', 'Cạnh tranh', 'Mẹo xanh', 'Eco Score')),
  repost_of uuid references public.community_posts(post_id) on delete cascade,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  unique (author_account_id, repost_of)
);

create table if not exists public.community_likes (
  post_id uuid not null references public.community_posts(post_id) on delete cascade,
  account_id integer not null references public.accounts(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (post_id, account_id)
);

create table if not exists public.community_comments (
  comment_id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.community_posts(post_id) on delete cascade,
  author_account_id integer not null references public.accounts(id) on delete cascade,
  author_name text not null default '',
  body text not null check (char_length(body) between 1 and 300),
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create index if not exists idx_community_posts_feed on public.community_posts(created_at desc) where deleted_at is null;
create index if not exists idx_community_comments_post on public.community_comments(post_id, created_at) where deleted_at is null;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('account-avatars', 'account-avatars', false, 5242880, array['image/jpeg','image/png','image/webp'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
