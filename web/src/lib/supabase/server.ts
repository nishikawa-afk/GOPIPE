import { createServerClient } from "@supabase/ssr";
import { createClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";

/** サーバ側の Supabase（ログイン中のユーザーとして動く。RLS が効く）。 */
export async function supabaseServer() {
  const store = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => store.getAll(),
        setAll: (list) => {
          try {
            list.forEach(({ name, value, options }) => store.set(name, value, options));
          } catch {
            // Server Component からは書けない。middleware 側で更新されるので無視でよい。
          }
        },
      },
    },
  );
}

/**
 * RLS をバイパスする管理用クライアント。組織への参加登録など、
 * 「まだ所属が無いから RLS では触れない」処理だけに使う。
 */
export function supabaseAdmin() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { autoRefreshToken: false, persistSession: false } },
  );
}

export type Membership = { orgId: string; slug: string; name: string; role: string };

/** ログイン中ユーザーと、その所属組織を取る。未ログイン/未所属は null。 */
export async function currentMembership(): Promise<
  { userId: string; email: string; org: Membership | null } | null
> {
  const sb = await supabaseServer();
  const {
    data: { user },
  } = await sb.auth.getUser();
  if (!user) return null;

  const { data } = await sb
    .from("memberships")
    .select("org_id, role, organizations(slug, name)")
    .eq("user_id", user.id)
    .limit(1)
    .maybeSingle();

  const org = data
    ? {
        orgId: data.org_id as string,
        role: data.role as string,
        slug: (data.organizations as unknown as { slug: string; name: string })?.slug,
        name: (data.organizations as unknown as { slug: string; name: string })?.name,
      }
    : null;

  return { userId: user.id, email: user.email ?? "", org };
}
