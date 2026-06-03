-- 0001_init.sql — GOPIPE 基盤：マルチテナント（組織・メンバー）
-- GOREFORM track-b の organizations/memberships を踏襲。
-- RLS は「自分が所属する組織のみ」。USING true は使わない。

create extension if not exists "uuid-ossp";

-- 組織（テナント＝設備工事会社）
create table if not exists organizations (
  id            uuid primary key default uuid_generate_v4(),
  slug          text unique not null,
  name          text not null,
  plan          text not null default 'free',
  contact_email text,
  active        boolean not null default true,
  created_at    timestamptz not null default now()
);

-- ユーザー × 組織 × ロール
create table if not exists memberships (
  id         uuid primary key default uuid_generate_v4(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  org_id     uuid not null references organizations(id) on delete cascade,
  role       text not null default 'member' check (role in ('owner','admin','member','viewer')),
  created_at timestamptz not null default now(),
  unique (user_id, org_id)
);

create index if not exists idx_memberships_user on memberships(user_id);
create index if not exists idx_memberships_org  on memberships(org_id);

-- 自分が所属する org_id 一覧（RLS から利用）
create or replace function current_org_ids()
returns setof uuid
language sql
stable
security definer
set search_path = public
as $$
  select org_id from memberships where user_id = auth.uid()
$$;

alter table organizations enable row level security;
alter table memberships   enable row level security;

-- organizations: 所属組織のみ参照。更新は owner/admin のみ。
drop policy if exists org_select on organizations;
create policy org_select on organizations
  for select using (id in (select current_org_ids()));

drop policy if exists org_update on organizations;
create policy org_update on organizations
  for update using (
    id in (select org_id from memberships
           where user_id = auth.uid() and role in ('owner','admin'))
  );

-- memberships: 自分の所属レコード、または同一組織のメンバーを参照。
drop policy if exists mem_select on memberships;
create policy mem_select on memberships
  for select using (user_id = auth.uid() or org_id in (select current_org_ids()));
