# Locale-separated knowledge（海外展開の土台 / VISION.md）

GOPIPE は**知識レイヤー**（辞書・単価・抽出プロンプト）を国コードで分離し、
同じAIエンジンで複数国に展開できるようにする。

## 解決順（`gopipe_takeoff.locale.resolve`）
1. `prompts/<locale>/<file>`
2. `prompts/<file>` ← flat = 日本語既定（既存資産・後方互換）
3. `prompts/ja/<file>`

アクティブなロケールは環境変数 `GOPIPE_LOCALE`（既定 `ja`）。
Streamlit UI ではサイドバーの **言語 / Locale** で切替。

## ロケール固有のもの
- `dictionary.yaml` — 正規名 / カテゴリ / 単位 / 別名
- `unit_prices.yaml` — 通貨別の単価・歩掛(labor_hours)
- `extraction.txt` — 抽出システムプロンプト（無ければ ja にフォールバック）

日本固有の機能（申請/予防保全/透明見積：municipalities, service_life,
emergency_catalog）は、国際化するまで flat（ja）のまま。

## 状況
- `ja` — フル（flat ファイル）
- `en` — Phase-1 **スケルトン**（starter 辞書＋USD単価）。ローンチ前に拡充する。
