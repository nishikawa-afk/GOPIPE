"use client";

import { useEffect, useState } from "react";

type Alias = {
  raw: string;
  canonical: string;
  category: string | null;
  unit: string | null;
};

export default function DictionaryList() {
  const [rows, setRows] = useState<Alias[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  async function load() {
    try {
      const res = await fetch("/api/dictionary", { cache: "no-store" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error ?? "読めませんでした");
      setRows(data.aliases ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRows([]);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function revoke(raw: string) {
    setBusy(raw);
    setError("");
    try {
      const res = await fetch("/api/dictionary", {
        method: "DELETE",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ raw }),
      });
      if (!res.ok) throw new Error("取り消せませんでした");
      setRows((cur) => (cur ?? []).filter((r) => r.raw !== raw));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  if (rows === null) return <p className="text-[15px] text-[var(--mut)]">読み込み中…</p>;

  return (
    <>
      {error && (
        <p className="mb-4 rounded-[11px] border border-[rgba(215,38,30,0.35)] bg-[rgba(215,38,30,0.08)] px-4 py-3 text-[14px] text-[#f2c7c4]">
          {error}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="text-[15px] text-[var(--mut)]">
          まだ覚えたものはありません。拾い出しの表で名前を直して「この直しを覚えさせる」を押すと、ここに貯まります。
        </p>
      ) : (
        <ul className="m-0 list-none space-y-2 p-0">
          {rows.map((r) => (
            <li
              key={r.raw}
              className="flex flex-wrap items-center justify-between gap-3 rounded-[11px] border border-[var(--line)] bg-[var(--panel)] px-5 py-3"
            >
              <span className="text-[15px]">
                <span className="text-[var(--mut)]">{r.raw}</span>
                <span className="mx-3 text-[var(--cyan)]">→</span>
                <span className="font-bold">{r.canonical}</span>
                {r.category && (
                  <span className="ml-3 text-[12.5px] text-[var(--mut)]">（{r.category}）</span>
                )}
              </span>
              <button
                onClick={() => revoke(r.raw)}
                disabled={busy === r.raw}
                className="rounded-[9px] border border-[var(--line)] px-4 py-1.5 text-[13px] text-[var(--mut)] hover:border-[var(--red)] hover:text-[var(--red)] disabled:opacity-50"
              >
                {busy === r.raw ? "取り消し中…" : "取り消す"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
