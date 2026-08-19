import { createBrowserClient } from "@supabase/ssr";

/** ブラウザ側の Supabase。anon キーしか持たないので、見える範囲は RLS が決める。 */
export function supabaseBrowser() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
