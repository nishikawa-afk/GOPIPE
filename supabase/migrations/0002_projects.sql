-- 0002_projects.sql — GOPIPE 案件・図面・拾い出し
-- 案件(projects) → 図面/成果物(project_files) → 拾い出し項目(takeoff_items)
-- すべて org_id スコープの RLS。

create table if not exists projects (
  id              uuid primary key default uuid_generate_v4(),
  org_id          uuid not null references organizations(id) on delete cascade,
  slug            text not null,
  title           text not null default '',
  status          text not null default 'draft'
                    check (status in ('draft','takeoff','estimated','submitted','done')),
  source_pdf_path text,                      -- Storage 上の設備図PDF
  item_count      integer not null default 0,
  total_amount    bigint  not null default 0, -- 見積合計（税込）
  municipality    text,                       -- 申請提出先（F-16）
  installed_year  integer,                    -- 予防保全用 布設年（F-17）
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (org_id, slug)
);
create index if not exists idx_projects_org on projects(org_id);

-- 成果物・添付（拾い出しxlsx / 見積xlsx / 発注xlsx / 申込md / 提案md / 図面pdf 等）
create table if not exists project_files (
  id           uuid primary key default uuid_generate_v4(),
  project_id   uuid not null references projects(id) on delete cascade,
  org_id       uuid not null references organizations(id) on delete cascade,
  kind         text not null,   -- source_pdf/takeoff_xlsx/estimate_xlsx/purchase_xlsx/application_md/maintenance_md/quote_md
  storage_path text not null,
  created_at   timestamptz not null default now()
);
create index if not exists idx_project_files_project on project_files(project_id);

-- 拾い出し項目（構造化保存。再見積・台帳・申請の元データ）
create table if not exists takeoff_items (
  id         uuid primary key default uuid_generate_v4(),
  project_id uuid not null references projects(id) on delete cascade,
  org_id     uuid not null references organizations(id) on delete cascade,
  category   text,
  name       text not null,
  spec       text,
  location   text,
  quantity   numeric not null default 0,
  unit       text,
  confidence numeric not null default 1.0,
  created_at timestamptz not null default now()
);
create index if not exists idx_takeoff_items_project on takeoff_items(project_id);

-- RLS: 全テーブル org スコープ（参照・書込とも所属組織に限定）
alter table projects      enable row level security;
alter table project_files enable row level security;
alter table takeoff_items enable row level security;

drop policy if exists projects_all on projects;
create policy projects_all on projects
  for all using      (org_id in (select current_org_ids()))
          with check (org_id in (select current_org_ids()));

drop policy if exists project_files_all on project_files;
create policy project_files_all on project_files
  for all using      (org_id in (select current_org_ids()))
          with check (org_id in (select current_org_ids()));

drop policy if exists takeoff_items_all on takeoff_items;
create policy takeoff_items_all on takeoff_items
  for all using      (org_id in (select current_org_ids()))
          with check (org_id in (select current_org_ids()));
