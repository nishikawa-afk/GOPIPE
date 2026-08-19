-- 0006_takeoff_corrections.sql — 修正の生データを会社の資産として残す
--
-- いまは「N件の修正を記録しました」と画面に出るのに、書き込み先の out/feedback.jsonl は
-- Vercel に存在しない（.vercelignore が out/ を除外）ため、本番では1件も残っていない。
-- 名称の言い換え（learned_aliases）だけが堀で、数量・仕様・拾い漏れ・過剰という
-- 積算の本丸が丸ごと落ちている状態だった。
--
-- ここに貯まるのは将来の few-shot / fine-tune の教材であり、
-- 「AIが何をどれだけ間違えたか」の唯一の記録でもある（谷を渡ったかの指標の分母）。

create table if not exists takeoff_corrections (
  id         uuid primary key default uuid_generate_v4(),
  org_id     uuid not null references organizations(id) on delete cascade,
  project_id uuid references projects(id) on delete set null,
  drawing_id uuid references drawings(id) on delete set null,
  item_id    uuid,                    -- takeoff_items.id（行が消えても記録は残す）
  kind       text not null default 'edit'
               check (kind in ('edit', 'added', 'removed')),
  before     jsonb,                   -- AIの下書き（added のときは null）
  after      jsonb,                   -- 人が確定した値（removed のときは null）
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);
create index if not exists idx_corrections_org on takeoff_corrections(org_id);
create index if not exists idx_corrections_project on takeoff_corrections(project_id);

alter table takeoff_corrections enable row level security;
drop policy if exists corrections_all on takeoff_corrections;
create policy corrections_all on takeoff_corrections
  for all using      (org_id in (select current_org_ids()))
          with check (org_id in (select current_org_ids()));
