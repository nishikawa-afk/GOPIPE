-- 0005_drawings_and_status.sql — 「昨日の続きが開く」ための器
--
-- いまの作りは 1案件=1回の拾い出し で、同じ物件名で2枚目の図面を流すと
-- 1枚目の明細が黙って全部消える（replace_takeoff_items が project 単位の全削除）。
-- 図面を独立した器にして、明細をどの図面の何ページ由来かで持てるようにする。
-- また「AIの下書き」と「人が確定した値」を行単位で区別する。ここが無いと、
-- 台帳に残るのは永久に AI が間違えたままの下書きになる。
--
-- 追加のみ。既存の列・データ・RLS は壊さない。

-- 図面（1案件に複数枚）
create table if not exists drawings (
  id           uuid primary key default uuid_generate_v4(),
  org_id       uuid not null references organizations(id) on delete cascade,
  project_id   uuid not null references projects(id) on delete cascade,
  storage_path text not null,
  file_name    text not null default '',
  page_count   integer,
  kind         text,                    -- 'cad' | 'scan'（/inspect の判定）
  status       text not null default 'done'
                 check (status in ('running','done','failed','partial')),
  warnings     jsonb not null default '[]'::jsonb,  -- 読めなかったページ等
  created_at   timestamptz not null default now()
);
create index if not exists idx_drawings_project on drawings(project_id);
create index if not exists idx_drawings_org on drawings(org_id);

alter table drawings enable row level security;
drop policy if exists drawings_all on drawings;
create policy drawings_all on drawings
  for all using      (org_id in (select current_org_ids()))
          with check (org_id in (select current_org_ids()));

-- 明細に「どの図面の何ページか」と「誰が確定したか」を持たせる
alter table takeoff_items add column if not exists drawing_id uuid references drawings(id) on delete cascade;
alter table takeoff_items add column if not exists page integer;
alter table takeoff_items add column if not exists source text;          -- text_table / reconciled 等
alter table takeoff_items add column if not exists raw_name text;        -- AIが読んだ生の名称（学習の鍵）
alter table takeoff_items add column if not exists qty_vision numeric;   -- 機器表と食い違った時の図面側の読み
alter table takeoff_items add column if not exists checks jsonb not null default '[]'::jsonb;
alter table takeoff_items add column if not exists status text not null default 'ai_draft'
  check (status in ('ai_draft', 'confirmed', 'added_by_human'));
alter table takeoff_items add column if not exists confirmed_by uuid references auth.users(id);
alter table takeoff_items add column if not exists confirmed_at timestamptz;
alter table takeoff_items add column if not exists updated_at timestamptz not null default now();

create index if not exists idx_takeoff_items_drawing on takeoff_items(drawing_id);
create index if not exists idx_takeoff_items_status on takeoff_items(org_id, status);

-- 誰が起こした案件か（一覧の並びと、後から聞ける相手のため）
alter table projects add column if not exists created_by uuid references auth.users(id);
alter table projects add column if not exists last_run_at timestamptz;
