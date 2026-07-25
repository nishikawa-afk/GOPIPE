"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabaseBrowser } from "@/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "signup") {
        const res = await fetch("/api/signup", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ email, password, code }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error ?? "登録に失敗しました");
      }
      const sb = supabaseBrowser();
      const { error: signInError } = await sb.auth.signInWithPassword({ email, password });
      if (signInError) {
        throw new Error(
          mode === "login"
            ? "メールかパスワードが違います"
            : "登録はできましたが、ログインに失敗しました",
        );
      }
      router.push("/app");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const field =
    "w-full rounded-[10px] border border-[var(--line)] bg-[var(--navy2)] px-4 py-3 text-[15px] text-[var(--ink)] placeholder:text-[var(--mut)] focus:border-[var(--cyan)] focus:outline-none";

  return (
    <main className="mx-auto flex w-full max-w-[480px] flex-1 flex-col justify-center px-5 py-16">
      <p className="m-0 text-[12px] font-bold tracking-[0.34em] text-[var(--cyan)]">
        GOPIPE
      </p>
      <h1 className="mt-2 mb-1 text-[28px] font-black">
        {mode === "login" ? "ログイン" : "はじめて使う"}
      </h1>
      <p className="mt-0 mb-7 text-[14px] text-[var(--mut)]">
        {mode === "login"
          ? "会社で使っているメールとパスワードを入れてください。"
          : "管理者から受け取った招待コードで登録します。パスワードはご自身で決めてください。"}
      </p>

      <form onSubmit={submit} className="flex flex-col gap-3">
        {mode === "signup" && (
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="招待コード"
            autoComplete="off"
            className={field}
          />
        )}
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="メールアドレス"
          autoComplete="username"
          className={field}
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={mode === "signup" ? "パスワード（10文字以上）" : "パスワード"}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          className={field}
        />

        {error && (
          <p className="m-0 rounded-[10px] border border-[rgba(215,38,30,0.35)] bg-[rgba(215,38,30,0.08)] px-4 py-3 text-[14px] text-[#f2c7c4]">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-2 rounded-[11px] bg-gradient-to-b from-[#ffab33] to-[var(--orange)] px-6 py-3.5 text-[16px] font-black text-[#241200] disabled:opacity-60"
        >
          {busy ? "処理中…" : mode === "login" ? "ログイン" : "登録してはじめる"}
        </button>
      </form>

      <button
        onClick={() => {
          setMode(mode === "login" ? "signup" : "login");
          setError("");
        }}
        className="mt-6 text-[14px] font-bold text-[var(--cyan)] hover:underline"
      >
        {mode === "login"
          ? "はじめて使う（招待コードで登録）→"
          : "← すでに登録済みの方はログイン"}
      </button>

      <a
        href="/"
        className="mt-10 text-[13px] text-[var(--mut)] hover:text-[var(--ink)]"
      >
        ログインせずに、お試しの拾い出しを見る →
      </a>
    </main>
  );
}
