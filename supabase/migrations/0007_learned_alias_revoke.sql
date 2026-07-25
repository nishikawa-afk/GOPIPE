-- 0007_learned_alias_revoke.sql — 誤って覚えさせた言い換えを取り消せるようにする
--
-- 「この直しを覚えさせる」は一度押すと全社の抽出プロンプトに効き続けるのに、
-- 取り消す手段がひとつも無かった。実際、説明書動画の収録中に誤った別名
-- （給水管(VP) → 全熱交換器）を1件作ってしまい、DBを直接触るしか戻す方法が無かった。
-- 社員全員に「覚えさせる」を教える前に、戻り道を用意する。
--
-- 物理削除ではなく論理削除。会社が育てた資産を、押し間違い1回で永久に失わせない。

alter table learned_aliases add column if not exists revoked_at timestamptz;
alter table learned_aliases add column if not exists revoked_by uuid references auth.users(id);

create index if not exists idx_learned_aliases_active
  on learned_aliases(org_id, locale) where revoked_at is null;
