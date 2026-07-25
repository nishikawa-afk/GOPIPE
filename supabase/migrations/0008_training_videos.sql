-- 0008_training_videos.sql — 使い方動画の置き場所
--
-- 社員がアプリの中からすぐ見られるようにする。図面の置き場所（drawings）と分けるのは、
-- こちらは「会社をまたいだ共通の教材」で、org ごとに閉じる必要がないため。
-- ただし公開はしない。動画にはクライアント名と業務の流れが映っているので、
-- ログインした人だけが見られる状態にする。

insert into storage.buckets (id, name, public)
values ('training', 'training', false)
on conflict (id) do nothing;

-- ログイン済みなら読める（書き込みは service_role のみ＝管理者が差し替える）
drop policy if exists training_read on storage.objects;
create policy training_read on storage.objects
  for select
  using (bucket_id = 'training' and auth.role() = 'authenticated');
