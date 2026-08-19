import { API_BASE, serverKey } from "@/lib/gopipe";
import { currentMembership } from "@/lib/supabase/server";

/**
 * 直した内容を、その会社の辞書（学習の堀）へ還元する。ログイン必須。
 * 組織はセッションから引く＝他社の辞書は絶対に触れない。
 */
export async function POST(req: Request) {
  const me = await currentMembership();
  if (!me?.org) {
    return Response.json({ error: "ログインが必要です" }, { status: 401 });
  }
  const key = serverKey();
  if (!key) return Response.json({ error: "サーバの設定が未完了です" }, { status: 503 });

  const { corrections } = await req.json();
  if (!Array.isArray(corrections) || corrections.length === 0) {
    return Response.json({ error: "記録する変更がありません" }, { status: 400 });
  }

  const res = await fetch(`${API_BASE}/learn`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-gopipe-key": key },
    body: JSON.stringify({
      org_slug: me.org.slug,
      project: "web",
      corrections,
    }),
  });
  if (!res.ok) {
    return Response.json({ error: "学習の記録に失敗しました" }, { status: 502 });
  }
  return Response.json(await res.json());
}
