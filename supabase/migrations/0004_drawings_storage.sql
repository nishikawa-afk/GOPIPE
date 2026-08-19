-- 0004_drawings_storage.sql — 設備図PDFの置き場（Supabase Storage）
--
-- Vercel のサーバレスはリクエストボディが 4.5MB までで、設備図PDFはそれを超える。
-- そこでブラウザ→Storage へ直接アップロードし、API にはパスだけ渡す。
-- パスの先頭フォルダを組織 slug にして、他社の図面が見えないようにする。
--   例: haruki/2026-07-26_1F給排水.pdf

insert into storage.buckets (id, name, public)
values ('drawings', 'drawings', false)
on conflict (id) do nothing;

-- 自分が所属する組織のフォルダだけ読み書きできる
drop policy if exists drawings_org_rw on storage.objects;
create policy drawings_org_rw on storage.objects
  for all
  using (
    bucket_id = 'drawings'
    and (storage.foldername(name))[1] in (
      select o.slug from organizations o where o.id in (select current_org_ids())
    )
  )
  with check (
    bucket_id = 'drawings'
    and (storage.foldername(name))[1] in (
      select o.slug from organizations o where o.id in (select current_org_ids())
    )
  );
