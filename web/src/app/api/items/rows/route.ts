import { currentMembership, supabaseServer } from "@/lib/supabase/server";

/**
 * 行の追加・削除。
 *
 * AIが拾い落とした部材を画面で足せないと、見つけた瞬間にExcelへ落ちて手作業に戻る。
 * 逆に拾い過ぎ（二重計上）を消せないと、数量が倍のまま見積に流れる。
 * どちらも takeoff_corrections に残す＝AIが何を落として何を出し過ぎたかの記録になる。
 */
export async function POST(req: Request) {
  const me = await currentMembership();
  if (!me?.org) return Response.json({ error: "ログインが必要です" }, { status: 401 });

  const { projectId, drawingId, item } = await req.json();
  if (!projectId || !item?.name?.trim()) {
    return Response.json({ error: "名称を入れてください" }, { status: 400 });
  }

  const sb = await supabaseServer();
  const row = {
    project_id: projectId,
    org_id: me.org.orgId,
    drawing_id: drawingId ?? null,
    name: String(item.name).trim(),
    spec: item.spec ?? null,
    quantity: Number(item.quantity) || 0,
    unit: item.unit ?? "",
    location: item.location ?? null,
    category: item.category ?? null,
    confidence: 1,
    page: item.page ?? 1,
    raw_name: null, // 人が足した行。AIの読みではないので学習の鍵にはしない
    status: "added_by_human",
    confirmed_by: me.userId,
    confirmed_at: new Date().toISOString(),
  };
  const { data, error } = await sb.from("takeoff_items").insert(row).select("id").single();
  if (error) return Response.json({ error: "追加できませんでした" }, { status: 500 });

  await sb.from("takeoff_corrections").insert({
    org_id: me.org.orgId,
    project_id: projectId,
    item_id: data.id,
    kind: "added",
    after: row,
    created_by: me.userId,
  });
  return Response.json({ id: data.id });
}

export async function DELETE(req: Request) {
  const me = await currentMembership();
  if (!me?.org) return Response.json({ error: "ログインが必要です" }, { status: 401 });

  const { id, projectId, before } = await req.json();
  if (!id) return Response.json({ error: "行が指定されていません" }, { status: 400 });

  const sb = await supabaseServer();
  const { error } = await sb.from("takeoff_items").delete().eq("id", id);
  if (error) return Response.json({ error: "消せませんでした" }, { status: 500 });

  await sb.from("takeoff_corrections").insert({
    org_id: me.org.orgId,
    project_id: projectId ?? null,
    item_id: id,
    kind: "removed",
    before: before ?? null,
    created_by: me.userId,
  });
  return Response.json({ ok: true });
}
