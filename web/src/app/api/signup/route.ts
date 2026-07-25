import { supabaseAdmin } from "@/lib/supabase/server";

type JoinCodes = Record<string, { slug: string; name: string }>;

/**
 * 招待コードでの初回登録。
 *
 * メール送信（マジックリンク）に頼らないのは、Supabase の既定SMTPが時間あたり数通で
 * 現場が止まるため。管理者がコードを渡し、担当者が自分でパスワードを決める形にする。
 * コードは会社ごと（GOPIPE_JOIN_CODES）。正しいコードのときだけ組織へ所属させる。
 */
export async function POST(req: Request) {
  const { email, password, code } = await req.json();
  if (!email || !password || !code) {
    return Response.json({ error: "メール・パスワード・招待コードを入力してください" }, { status: 400 });
  }
  if (String(password).length < 10) {
    return Response.json({ error: "パスワードは10文字以上にしてください" }, { status: 400 });
  }

  let codes: JoinCodes = {};
  try {
    codes = JSON.parse(process.env.GOPIPE_JOIN_CODES || "{}");
  } catch {
    return Response.json({ error: "サーバの設定に問題があります" }, { status: 500 });
  }
  const org = codes[String(code).trim()];
  if (!org) {
    return Response.json({ error: "招待コードが違います" }, { status: 401 });
  }

  const admin = supabaseAdmin();

  // 組織（無ければ作る）
  const { data: orgRow, error: orgErr } = await admin
    .from("organizations")
    .upsert({ slug: org.slug, name: org.name }, { onConflict: "slug" })
    .select("id")
    .single();
  if (orgErr || !orgRow) {
    return Response.json({ error: "組織の準備に失敗しました" }, { status: 500 });
  }

  // ユーザー作成。メール確認は管理者が招待コードを渡した時点で済んでいる扱い。
  const { data: created, error: userErr } = await admin.auth.admin.createUser({
    email: String(email).trim(),
    password: String(password),
    email_confirm: true,
  });
  if (userErr || !created?.user) {
    const already = /already/i.test(userErr?.message ?? "");
    return Response.json(
      {
        error: already
          ? "このメールは登録済みです。ログインしてください。"
          : "登録に失敗しました",
      },
      { status: already ? 409 : 500 },
    );
  }

  const { error: memErr } = await admin
    .from("memberships")
    .upsert(
      { user_id: created.user.id, org_id: orgRow.id, role: "member" },
      { onConflict: "user_id,org_id" },
    );
  if (memErr) {
    return Response.json({ error: "組織への追加に失敗しました" }, { status: 500 });
  }

  return Response.json({ ok: true, org: org.name });
}
