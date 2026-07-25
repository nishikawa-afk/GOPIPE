import { API_BASE } from "@/lib/gopipe";

/** 確定した明細を Excel にして返す（エンジン側 /export/xlsx の中継）。 */
export async function POST(req: Request) {
  const body = await req.json();
  const items = Array.isArray(body?.items) ? body.items : [];
  if (items.length === 0) {
    return Response.json({ error: "明細が空です" }, { status: 400 });
  }

  const res = await fetch(`${API_BASE}/export/xlsx`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ items }),
  });
  if (!res.ok) {
    return Response.json(
      { error: `Excel 生成に失敗しました (${res.status})` },
      { status: 502 },
    );
  }

  return new Response(await res.arrayBuffer(), {
    headers: {
      "content-type":
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "content-disposition": 'attachment; filename="GOPIPE_takeoff.xlsx"',
    },
  });
}
