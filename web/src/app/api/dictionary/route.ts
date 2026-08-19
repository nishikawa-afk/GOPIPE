import { API_BASE, serverKey } from "@/lib/gopipe";
import { currentMembership } from "@/lib/supabase/server";

/** その会社が覚えた言い換えの一覧。組織はセッションから引く。 */
export async function GET() {
  const me = await currentMembership();
  if (!me?.org) return Response.json({ error: "ログインが必要です" }, { status: 401 });
  const key = serverKey();
  if (!key) return Response.json({ error: "サーバの設定が未完了です" }, { status: 503 });

  const res = await fetch(
    `${API_BASE}/learned?org_slug=${encodeURIComponent(me.org.slug)}`,
    { headers: { "x-gopipe-key": key }, cache: "no-store" },
  );
  if (!res.ok) return Response.json({ error: "辞書を読めませんでした" }, { status: 502 });
  return Response.json(await res.json());
}

/**
 * 覚え間違いの取り消し。
 *
 * 一度覚えさせた言い換えは全社の読み取りに効き続けるので、戻り道が要る。
 * 論理削除なので、同じ内容をもう一度教えれば復活する。
 */
export async function DELETE(req: Request) {
  const me = await currentMembership();
  if (!me?.org) return Response.json({ error: "ログインが必要です" }, { status: 401 });
  const key = serverKey();
  if (!key) return Response.json({ error: "サーバの設定が未完了です" }, { status: 503 });

  const { raw } = await req.json();
  if (!raw) return Response.json({ error: "対象がありません" }, { status: 400 });

  const url = `${API_BASE}/learned?org_slug=${encodeURIComponent(me.org.slug)}&raw=${encodeURIComponent(raw)}`;
  const res = await fetch(url, { method: "DELETE", headers: { "x-gopipe-key": key } });
  if (!res.ok) return Response.json({ error: "取り消せませんでした" }, { status: 502 });
  return Response.json({ ok: true });
}
