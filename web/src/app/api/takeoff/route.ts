import { NextResponse } from "next/server";
import { API_BASE } from "@/lib/gopipe";

/**
 * 公開デモの拾い出し。
 *
 * ここは誰でも叩ける口なので provider は mock に固定し、persist（顧客DBへの書き込み）も
 * 渡さない。実図面の解析とDB保存はログイン後の経路で開ける（Supabase Auth 導入時）。
 * ブラウザから直接エンジンAPIを叩かせず必ずこの中継を通すのは、後から認証と
 * レート制限を1か所で足せるようにするため。
 */
export async function POST() {
  const form = new FormData();
  form.set("provider", "mock");

  const res = await fetch(`${API_BASE}/takeoff`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    return NextResponse.json(
      { error: `拾い出しに失敗しました (${res.status})`, detail: detail.slice(0, 300) },
      { status: 502 },
    );
  }
  return NextResponse.json(await res.json());
}
