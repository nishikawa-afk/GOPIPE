-- 0003_learned_aliases.sql — 学習の堀（ユーザー修正→正規名の永続学習）
-- 生の名称(raw, NFKC正規化済) → 正規名/カテゴリ/単位。org スコープの RLS。
-- 拾い出しの分類(classify)に統合され、使うほど精度が上がる「データの堀」。

create table if not exists learned_aliases (
  id         uuid primary key default uuid_generate_v4(),
  org_id     uuid not null references organizations(id) on delete cascade,
  raw        text not null,           -- 正規化済みの生の名称（AI出力のゆれ）
  canonical  text not null,           -- 学習後の正規名
  category   text,
  unit       text,
  hits       integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (org_id, raw)
);
create index if not exists idx_learned_aliases_org on learned_aliases(org_id);

alter table learned_aliases enable row level security;

drop policy if exists learned_aliases_all on learned_aliases;
create policy learned_aliases_all on learned_aliases
  for all using      (org_id in (select current_org_ids()))
          with check (org_id in (select current_org_ids()));
