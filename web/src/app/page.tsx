"use client";

import { useMemo, useState } from "react";
import { confidenceLevel, type TakeoffItem } from "@/lib/gopipe";

type Row = TakeoffItem & { id: number; edited: boolean };

const BADGE: Record<string, { mark: string; label: string }> = {
  low: { mark: "🔴", label: "要確認" },
  mid: { mark: "🟡", label: "念のため確認" },
  high: { mark: "🟢", label: "そのままでOK" },
};

export default function Home() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [busy, setBusy] = useState<"" | "takeoff" | "excel">("");
  const [error, setError] = useState("");

  const warnCount = useMemo(
    () => (rows ?? []).filter((r) => confidenceLevel(r.confidence) === "low").length,
    [rows],
  );
  const editedCount = useMemo(() => (rows ?? []).filter((r) => r.edited).length, [rows]);

  async function runTakeoff() {
    setBusy("takeoff");
    setError("");
    try {
      const res = await fetch("/api/takeoff", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error ?? "失敗しました");
      // 要確認(🔴)を上に集めて、その中は確度の低い順。直すべき行から目に入るように。
      const items: TakeoffItem[] = data.items ?? [];
      const sorted = [...items].sort((a, b) => {
        const aw = confidenceLevel(a.confidence) === "low" ? 0 : 1;
        const bw = confidenceLevel(b.confidence) === "low" ? 0 : 1;
        return aw - bw || a.confidence - b.confidence;
      });
      setRows(sorted.map((it, i) => ({ ...it, id: i, edited: false })));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  function edit(id: number, patch: Partial<Row>) {
    setRows((cur) =>
      (cur ?? []).map((r) => (r.id === id ? { ...r, ...patch, edited: true } : r)),
    );
  }

  async function downloadExcel() {
    if (!rows?.length) return;
    setBusy("excel");
    setError("");
    try {
      const res = await fetch("/api/export", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          items: rows.map((r) => ({
            name: r.name,
            spec: r.spec,
            quantity: r.quantity,
            unit: r.unit,
            location: r.location,
            category: r.category,
            // 人が直した行は確定扱い（Streamlit 版と同じ考え方）
            confidence: r.edited ? 1 : r.confidence,
          })),
        }),
      });
      if (!res.ok) throw new Error("Excel の生成に失敗しました");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "GOPIPE_拾い出し.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  return (
    <main className="mx-auto w-full max-w-[1100px] px-5 pb-24">
      <header className="border-b border-[var(--line)] pt-14 pb-9">
        <p className="m-0 text-[12px] font-bold tracking-[0.34em] text-[var(--cyan)]">
          PIPING · HVAC · INSULATION — AI TAKEOFF
        </p>
        <h1 className="my-2 bg-gradient-to-b from-[#eaf6ff] to-[#8fd3f4] bg-clip-text text-[clamp(40px,9vw,76px)] font-black leading-[0.95] text-transparent">
          GOPIPE
        </h1>
        <p className="m-0 text-[clamp(18px,3vw,26px)] font-extrabold">
          未来へ、<span className="text-[var(--cyan)]">PIPE</span>を架ける。
          <span className="text-[var(--red)]"> AIは提案、確定は人。</span>
        </p>
        <p className="mt-3 mb-0 max-w-[62ch] text-[15px] text-[var(--mut)]">
          設備図から拾い出した明細を、その場で直して確定できます。ログイン不要のお試しでは、
          サンプル図面の結果が出ます。
        </p>
      </header>

      <section className="py-10">
        <div className="flex flex-wrap items-center gap-4">
          <button
            onClick={runTakeoff}
            disabled={busy !== ""}
            className="inline-flex items-center gap-3 rounded-[13px] bg-gradient-to-b from-[#ffab33] to-[var(--orange)] px-7 py-4 text-[18px] font-black text-[#241200] shadow-[0_10px_28px_rgba(247,148,30,0.28)] transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy === "takeoff" ? "拾い出し中…" : "拾い出しを実行"}
            <span className="text-[20px] leading-none">▶</span>
          </button>
          <a
            href="https://gopipe.vercel.app/share"
            className="text-[14px] font-bold text-[var(--cyan)] hover:underline"
          >
            動画・マンガはこちら →
          </a>
        </div>

        {error && (
          <p className="mt-5 rounded-[11px] border border-[rgba(215,38,30,0.35)] bg-[rgba(215,38,30,0.08)] px-4 py-3 text-[14px] text-[#f2c7c4]">
            {error}
          </p>
        )}

        {rows && (
          <>
            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              {[
                { k: "抽出した明細", v: `${rows.length} 件`, c: "var(--ink)" },
                { k: "要確認（🔴）", v: `${warnCount} 件`, c: "var(--red)" },
                { k: "あなたが直した行", v: `${editedCount} 件`, c: "var(--cyan)" },
              ].map((m) => (
                <div
                  key={m.k}
                  className="rounded-[11px] border border-[var(--line)] bg-[var(--panel)] px-4 py-3"
                >
                  <p className="m-0 text-[12px] font-bold tracking-wider text-[var(--mut)]">
                    {m.k}
                  </p>
                  <p className="tabular m-0 text-[26px] font-black" style={{ color: m.c }}>
                    {m.v}
                  </p>
                </div>
              ))}
            </div>

            <p className="mt-5 text-[14px] text-[var(--mut)]">
              AIの下書きです。🔴の行を上にまとめてあります。数量・名称はその場で直せます。
              直した行は確定扱いになります。
            </p>

            <div className="mt-4 overflow-x-auto rounded-[13px] border border-[var(--line)] bg-[var(--navy2)]">
              <table className="w-full min-w-[860px] border-collapse text-[14px]">
                <thead>
                  <tr className="border-b border-[var(--line)] text-left text-[12px] tracking-wider text-[var(--mut)]">
                    <th className="px-3 py-3 font-bold">確度</th>
                    <th className="px-3 py-3 font-bold">名称</th>
                    <th className="px-3 py-3 font-bold">仕様</th>
                    <th className="px-3 py-3 text-right font-bold">数量</th>
                    <th className="px-3 py-3 font-bold">単位</th>
                    <th className="px-3 py-3 font-bold">カテゴリ</th>
                    <th className="px-3 py-3 font-bold">場所</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const badge = BADGE[confidenceLevel(r.confidence)];
                    return (
                      <tr
                        key={r.id}
                        className="border-b border-[var(--line)] last:border-0 hover:bg-[rgba(86,204,242,0.04)]"
                      >
                        <td className="px-3 py-2 whitespace-nowrap">
                          <span title={r.edited ? "あなたが直した行" : badge.label}>
                            {r.edited ? "✅" : badge.mark}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={r.name}
                            onChange={(e) => edit(r.id, { name: e.target.value })}
                            className="w-full min-w-[180px] rounded-md border border-transparent bg-transparent px-2 py-1 hover:border-[var(--line)] focus:border-[var(--cyan)] focus:outline-none"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={r.spec ?? ""}
                            onChange={(e) => edit(r.id, { spec: e.target.value })}
                            className="w-full min-w-[120px] rounded-md border border-transparent bg-transparent px-2 py-1 text-[var(--mut)] hover:border-[var(--line)] focus:border-[var(--cyan)] focus:text-[var(--ink)] focus:outline-none"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            step="0.1"
                            value={r.quantity}
                            onChange={(e) => edit(r.id, { quantity: Number(e.target.value) })}
                            className="tabular w-[90px] rounded-md border border-transparent bg-transparent px-2 py-1 text-right hover:border-[var(--line)] focus:border-[var(--cyan)] focus:outline-none"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={r.unit}
                            onChange={(e) => edit(r.id, { unit: e.target.value })}
                            className="w-[70px] rounded-md border border-transparent bg-transparent px-2 py-1 hover:border-[var(--line)] focus:border-[var(--cyan)] focus:outline-none"
                          />
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-[var(--mut)]">
                          {r.category ?? ""}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-[var(--mut)]">
                          {r.location ?? ""}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-4">
              <button
                onClick={downloadExcel}
                disabled={busy !== ""}
                className="rounded-[11px] border border-[var(--cyan)] px-6 py-3 text-[15px] font-bold text-[var(--cyan)] transition hover:bg-[rgba(86,204,242,0.08)] disabled:opacity-60"
              >
                {busy === "excel" ? "作成中…" : "Excel で書き出す"}
              </button>
              <p className="m-0 max-w-[46ch] text-[13px] text-[var(--mut)]">
                直した内容を次回の精度に反映（学習）できるのは、ログインした社内利用のときだけです。
                お試しでは会社の辞書を汚さないよう記録しません。
              </p>
            </div>
          </>
        )}
      </section>

      <footer className="border-t border-[var(--line)] pt-7 text-center text-[12.5px] text-[var(--mut)]">
        GOPIPE — 株式会社and° / 設備積算AI
      </footer>
    </main>
  );
}
