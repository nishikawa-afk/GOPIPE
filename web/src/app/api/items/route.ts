import { currentMembership, supabaseServer } from "@/lib/supabase/server";

type Patch = {
  id: string;
  before: Record<string, unknown>;
  after: {
    name?: string;
    spec?: string | null;
    quantity?: number;
    unit?: string;
    category?: string | null;
    location?: string | null;
  };
};

/**
 * 人が直した行を、その場で台帳に確定させる。
 *
 * ボタンを押させない（＝入力を増やさない）ために、画面が触った行だけを黙って送る。
 * 組織はセッションから引き、書き込みはユーザー権限（RLS）で行う。
 * 直した事実は takeoff_corrections にも残す＝これが会社の資産になる生データ。
 */
export async function PATCH(req: Request) {
  const me = await currentMembership();
  if (!me?.org) return Response.json({ error: "ログインが必要です" }, { status: 401 });

  const { projectId, patches } = (await req.json()) as {
    projectId?: string;
    patches?: Patch[];
  };
  if (!Array.isArray(patches) || patches.length === 0) {
    return Response.json({ saved: 0 });
  }

  const sb = await supabaseServer();
  const now = new Date().toISOString();
  let saved = 0;
  const failed: string[] = [];

  for (const p of patches) {
    if (!p?.id) continue;
    const { error } = await sb
      .from("takeoff_items")
      .update({
        name: p.after.name,
        spec: p.after.spec ?? null,
        quantity: p.after.quantity,
        unit: p.after.unit,
        category: p.after.category ?? null,
        location: p.after.location ?? null,
        status: "confirmed",
        confirmed_by: me.userId,
        confirmed_at: now,
        updated_at: now,
      })
      .eq("id", p.id);
    if (error) {
      failed.push(p.id);
      continue;
    }
    saved += 1;
    // 修正の生データ。失敗しても確定そのものは巻き戻さない（本体は保存済み）。
    await sb.from("takeoff_corrections").insert({
      org_id: me.org.orgId,
      project_id: projectId ?? null,
      item_id: p.id,
      kind: "edit",
      before: p.before,
      after: p.after,
      created_by: me.userId,
    });
  }

  // 実際に保存できた件数だけ返す。画面には「保存しました」と嘘をつかせない。
  return Response.json({ saved, failed });
}
