import { redirect } from "next/navigation";
import Link from "next/link";
import { currentMembership, supabaseAdmin } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

/**
 * 使い方（3分の動画）。
 *
 * 動画は公開バケットに置かない。クライアント名と業務の流れが映っているので、
 * ログインした人にだけ、その場かぎりの署名付きURLで見せる。
 */
const CHAPTERS = [
  { key: "ch1.mp4", title: "まず、入る", sec: "0:12", note: "メールとパスワードで入る" },
  { key: "ch2.mp4", title: "図面を入れる", sec: "0:41", note: "選んで、物件名を入れて、実行" },
  { key: "ch3.mp4", title: "うちの言葉に直す", sec: "0:56", note: "表の欄を押して打ち直す" },
  { key: "ch4.mp4", title: "覚えさせる", sec: "0:36", note: "次から会社の言葉で出る" },
  { key: "ch5.mp4", title: "翌日、つづきを開く", sec: "0:21", note: "物件一覧から昨日の表へ" },
  { key: "ch6.mp4", title: "いつでも取り消せる", sec: "0:25", note: "覚え間違いは戻せる" },
];

export default async function GuidePage() {
  const me = await currentMembership();
  if (!me) redirect("/login");

  // 1時間だけ有効なURLを、この画面を開いた人のために作る
  const admin = supabaseAdmin();
  const keys = ["full.mp4", "poster.jpg", ...CHAPTERS.map((c) => c.key)];
  const { data } = await admin.storage.from("training").createSignedUrls(keys, 3600);
  const url = (k: string) => data?.find((d) => d.path === k)?.signedUrl ?? "";

  return (
    <main className="mx-auto w-full max-w-[900px] px-5 pb-24">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] py-6">
        <div>
          <p className="m-0 text-[12px] font-bold tracking-[0.3em] text-[var(--cyan)]">GOPIPE</p>
          <p className="m-0 text-[20px] font-black">使い方（3分）</p>
        </div>
        <Link href="/app" className="text-[14px] font-bold text-[var(--cyan)] hover:underline">
          ← 拾い出しに戻る
        </Link>
      </header>

      <section className="py-8">
        <p className="mt-0 mb-6 max-w-[62ch] text-[15px] text-[var(--mut)]">
          この画面の操作を、実際の画面のまま撮ったものです。はじめての方は通しで一度、
          あとは分からなくなった章だけ見てください。
        </p>

        <video
          controls
          playsInline
          preload="metadata"
          poster={url("poster.jpg")}
          className="w-full rounded-[13px] border border-[var(--line)] bg-black"
        >
          <source src={url("full.mp4")} type="video/mp4" />
        </video>

        <p className="mt-3 mb-8 text-[13px] text-[var(--mut)]">
          通し版 3分11秒 ／ 図面を入れる → 直す → 覚えさせる → 翌日つづきを開く
        </p>

        <h2 className="mb-3 text-[16px] font-black">章ごとに見る</h2>
        <ul className="m-0 grid list-none gap-4 p-0 sm:grid-cols-2">
          {CHAPTERS.map((c, i) => (
            <li
              key={c.key}
              className="rounded-[13px] border border-[var(--line)] bg-[var(--panel)] p-4"
            >
              <video
                controls
                playsInline
                preload="none"
                className="w-full rounded-[9px] bg-black"
              >
                <source src={url(c.key)} type="video/mp4" />
              </video>
              <p className="mt-3 mb-1 text-[15px] font-bold">
                {i + 1}. {c.title}
                <span className="ml-2 text-[12.5px] font-normal text-[var(--mut)]">{c.sec}</span>
              </p>
              <p className="m-0 text-[13px] text-[var(--mut)]">{c.note}</p>
            </li>
          ))}
        </ul>

        <div className="mt-10 rounded-[13px] border border-[var(--line)] bg-[var(--navy2)] p-5">
          <p className="mt-0 mb-2 text-[15px] font-bold">まず自分で触ってみる</p>
          <p className="mt-0 mb-3 text-[14px] text-[var(--mut)]">
            動画と同じ図面を用意しています。物件名に「練習」と入れて試してください。
          </p>
          <a
            href="/sample/practice-drawing.pdf"
            download="GoPipe練習用_中央ビル_1F給排水.pdf"
            className="text-[14px] font-bold text-[var(--cyan)] hover:underline"
          >
            練習用の設備図をダウンロード →
          </a>
        </div>
      </section>
    </main>
  );
}
