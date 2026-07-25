/**
 * GOPIPE エンジン API（Vercel 上の FastAPI）への窓口。
 *
 * GOPIPE_API_KEY は「自社の Claude キーを消費する操作」と「顧客DBへの書き込み」を
 * 開けるための鍵。ブラウザには絶対に出さず、この Next.js のサーバ側だけが持つ。
 * 公開デモ（provider=mock）は鍵なしで通るので、鍵を付けずに転送する。
 */
export const API_BASE = process.env.GOPIPE_API_BASE ?? "https://gopipe.vercel.app";

/** 鍵が要る操作かどうか。要るのにサーバに鍵が無ければ呼ばない（黙って落とさない）。 */
export function serverKey(): string | null {
  return process.env.GOPIPE_API_KEY || null;
}

export type TakeoffItem = {
  category: string | null;
  name: string;
  spec: string | null;
  location: string | null;
  quantity: number;
  unit: string;
  confidence: number;
};

/** 🔴＝要確認。Streamlit 版と同じ 0.7 / 0.85 の線を守る。 */
export function confidenceLevel(c: number): "low" | "mid" | "high" {
  if (c < 0.7) return "low";
  if (c < 0.85) return "mid";
  return "high";
}
