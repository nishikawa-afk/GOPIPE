import { redirect } from "next/navigation";
import { currentMembership } from "@/lib/supabase/server";
import Workbench from "./Workbench";

export default async function AppPage() {
  const me = await currentMembership();
  if (!me) redirect("/login");

  if (!me.org) {
    return (
      <main className="mx-auto w-full max-w-[560px] px-5 py-24">
        <h1 className="text-[24px] font-black">組織に所属していません</h1>
        <p className="text-[15px] text-[var(--mut)]">
          {me.email} は、まだどの会社にも紐づいていません。
          管理者に招待コードを確認して、登録し直してください。
        </p>
        <a href="/login" className="font-bold text-[var(--cyan)]">
          ← ログイン画面へ
        </a>
      </main>
    );
  }

  return <Workbench orgSlug={me.org.slug} orgName={me.org.name} email={me.email} />;
}
