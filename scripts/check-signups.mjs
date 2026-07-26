#!/usr/bin/env node
/**
 * 招待コード露出後に、身に覚えのない登録が無いかを見る。
 *   node scripts/check-signups.mjs            … 直近30日
 *   node scripts/check-signups.mjs 2026-07-20 … その日以降
 *
 * 出すのはメール・作成日時・所属組織だけ（鍵やパスワードは扱わない）。
 */
import { readFileSync } from "node:fs";
import { createClient } from "@supabase/supabase-js";

const env = Object.fromEntries(
  readFileSync(new URL("../web/.env.local", import.meta.url), "utf8")
    .split("\n").filter((l) => l.includes("=") && !l.trim().startsWith("#"))
    .map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()]),
);

const admin = createClient(env.NEXT_PUBLIC_SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
});

const since = process.argv[2]
  ? new Date(process.argv[2])
  : new Date(Date.now() - 30 * 86400_000);

const { data: orgs } = await admin.from("organizations").select("id,slug,name");
const orgById = Object.fromEntries((orgs ?? []).map((o) => [o.id, o]));
const { data: mems } = await admin.from("memberships").select("user_id,org_id,role");
const orgOfUser = Object.fromEntries((mems ?? []).map((m) => [m.user_id, m]));

let page = 1, rows = [];
for (;;) {
  const { data, error } = await admin.auth.admin.listUsers({ page, perPage: 200 });
  if (error) { console.error("読み出しに失敗:", error.message); process.exit(1); }
  rows.push(...data.users);
  if (data.users.length < 200) break;
  page += 1;
}

const recent = rows
  .filter((u) => new Date(u.created_at) >= since)
  .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

console.log(`\n${since.toISOString().slice(0, 10)} 以降の登録: ${recent.length}件 / 全${rows.length}件\n`);
for (const u of recent) {
  const m = orgOfUser[u.id];
  const org = m ? orgById[m.org_id] : null;
  console.log(
    `  ${new Date(u.created_at).toLocaleString("ja-JP")}  ${u.email ?? "(メール無し)"}  ` +
    `→ ${org ? org.name : "所属なし"}${m ? ` (${m.role})` : ""}`,
  );
}
console.log(
  recent.length
    ? "\n心当たりの無いメールがあれば、Supabase の Authentication から削除してください。\n"
    : "\n身に覚えのない登録はありません。\n",
);
