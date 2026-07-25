# SKILLS.md — GOPIPE 開発引き継ぎ（別セッション用ハンドオフ）

> 新しい開発セッション（Claude / Codex / 人間）はまずこれを読む。
> 全体概要は [`AGENTS.md`](AGENTS.md)、北極星は [`VISION.md`](VISION.md)。
> ⚠️ **このリポジトリは public**。このファイルにシークレット（APIキー・DBパスワード・service_role）を書かないこと。実値は `.env.local` / Streamlit Secrets / Vercel env のみ。

最終更新: 2026-07-06 ／ ブランチ `deploy/vercel-supabase-prep` ／ HEAD `19f2b3d` ／ pytest **71本 green**

---

## 1. 30秒サマリ

**GOPIPE** = 設備図PDF（配管・**空調**・**断熱**）→ 拾い出し → 見積/申請/予防保全 帳票までを一気通貫するAIエンジン。
- スタック: Python 3.11 / FastAPI（`api/main.py`）+ Streamlit（`webui/app.py`）+ Supabase（PostgREST/service_role）。エンジン本体は `src/gopipe_takeoff/`。
- 母体 GOREFORM の拾い出しエンジンを配管・空調・断熱に特化させたもの。姉妹に GOFIRE（消防）。
- 設計思想: **「AIは提案・確定は人」**。`ANTHROPIC_API_KEY` 無しでも **mockモード**でパイプライン全体が動く。
- 北極星: 7年後(〜2033)に日本の空調積算技術を海外展開 → だから**ロケール分離・通貨/税率抽象化・i18n**を先行実装済み（`VISION.md`）。

---

## 2. すぐ動かす（コマンド）

```bash
cd /Users/ishikawa/Documents/Dev/GOPIPE

# ── テスト（71本）──  ※ cd 後の複合コマンドで cwd がズレる事故があるので絶対パス推奨
.venv/bin/python -m pytest -q

# ── Streamlit UI（触れる本体・mockで即動く）──
.venv/bin/streamlit run webui/app.py

# ── API サーバー ──
make run              # または: .venv/bin/uvicorn api.main:app --reload

# ── 型/ビルド確認（Python なので pytest が実質のCI）──
.venv/bin/python -m pytest -q
```

**ハマりどころ**: `cd A && .venv/bin/python` のように複合すると cwd が持ち越されて venv を見失うことがある。困ったら**絶対パス** `/Users/ishikawa/Documents/Dev/GOPIPE/.venv/bin/python` を使う。

---

## 3. アーキテクチャ地図（`src/gopipe_takeoff/`）

| モジュール | 役割 |
|---|---|
| `pipeline.py` | 一気通貫オーケストレーション（PDF→抽出→分類→単価→帳票） |
| `pdf_loader.py` | PDF読込・タイル分割・**スキャン図の自動画質補正**（`_enhance_png`） |
| `extractor.py` | LLM抽出。機器表突合・**学習ヒント自動注入**（`_learned_hint`） |
| `equipment_table.py` | 機器表テキストを構造化（確定情報ソース） |
| `classifier.py` / `dictionary.py` | 品目正規化・カテゴリ/単位辞書（`add_learned` で成長） |
| `pricer.py` / `estimate.py` / `estimate_pdf.py` | 単価付け・見積・**見積書PDF（ja/en i18n・通貨/税率対応）** |
| `excel_writer.py` | F-12/15/16/17 帳票（xlsx） |
| `application.py` / `maintenance.py` / `emergency.py` | 申請書・予防保全・緊急対応 |
| `insulation_area.py` / `site_measure.py` | 断熱面積算出・現地実測（LiDAR数値の半自動連携） |
| `riser_estimate.py` | **系統図×階高の立管延長計算**（柱④） |
| `legend_count.py` / `symbol_match.py` | **凡例記号カウント**（テキスト段階1 / numpy-NCC の CV 段階2＝ローカル専用） |
| `validate_items.py` | **整合チェック**（数量0/単位×カテゴリ不一致/外れ値/重複をフラグ） |
| `benchmark.py` / `feedback.py` | 正解突合・信頼度・フィードバック |
| `locale.py` | **ロケール解決**（`prompts/{locale}/`→flat(ja既定)→`prompts/ja/`）＋`money_for`（通貨/税率） |
| `learned.py` / `store.py` | **学習の堀**（ローカルJSON `<locale>/<raw>` ＋ Supabase 永続化） |
| `marker.py` | 図面プレビューのマーカー描画 |

`prompts/` … `extraction.txt`・`dictionary.yaml`・`unit_prices.yaml` ほか。`prompts/en/` に英語ロケール一式（HVAC/MEP 辞書・USD単価・英語抽出プロンプト）。新しい国は `prompts/<国>/` を置くだけ。

---

## 4. 実装済みの「武器」（どこに何があるか）

### 精度改革 5本の柱
1. **機器表テキスト抽出を本線統合** — `extractor.reconcile_with_text_table`（確定情報で数量上書き・漏れ補完・ズレ警告、source/信頼度をExcel備考へ）
2. **凡例ドリブン記号カウント** — `legend_count.py`（段階1・テキスト層）＋ `symbol_match.py`（段階2・numpy NCC の CV、opencv不使用＝サーバレス肥大回避、ローカル専用）
3. **高解像度タイル＋多パス** — `pdf_loader.py`（grid/two_pass）
4. **系統図×階高の延長計算** — `riser_estimate.py`（立管=階高×階数×本数＋横引き/継手/弁）
5. **機器表突合＋信頼度** — `benchmark.py` / `samples/truth_template.csv` / `scripts/run_benchmark.py`

### 追加の精度施策 4点
6. 抽出プロンプトに**数量集約 few-shot**（`prompts/extraction.txt` ja / `prompts/en/extraction.txt` en）
7. **修正の few-shot 自動注入** — `extractor._learned_hint()`（使うほど抽出が賢くなる）
8. **ルールベース整合チェック** — `validate_items.py` → webui レビュー表にチェック列
9. **スキャン図の自動画質補正** — `pdf_loader._enhance_png`（自動コントラスト+鮮鋭化、テキスト層<50字で発動）

### 学習の堀（辞書自動成長・永続化）
- `learned.py`: `record_alias` / `load_aliases`（ローカルJSON、キー `<locale>/<raw>`）
- `store.py`: `record_learned_alias` / `load_learned_aliases`（Supabase・org×locale スコープ）
- `dictionary.TakeoffDictionary.add_learned()` で辞書へ反映
- migration `supabase/migrations/0003_learned_aliases.sql`（`org_id×locale×raw` 一意、org スコープRLS）

### ロケール分離 / i18n（海外展開の土台）
- `locale.py`: `resolve()` / `current_locale()` / `available_locales()` / `MONEY`（ja=¥・10% ⇄ en=$・Sales Tax）/ `money_for()`。環境変数 `GOPIPE_LOCALE` で切替、後方互換（flat=ja）。
- `estimate_pdf.py`: `_LABELS`（ja/en）＋ `locale`/`tax_label` 引数 → **完全英語 QUOTATION/USD をPDFまで実証済**。
- `webui/app.py`: 言語セレクタ ＋ `_t()`/`I18N`（ja/en）でヒーロー/実行/タブを多言語化。
- 詳細と原則は `VISION.md`。

---

## 5. デプロイ構成（公開URL）

| 面 | URL / 状態 |
|---|---|
| **Streamlit UI（触れる本体・公開）** | https://gopipe-3ceu7ceswzmfypvvpxb7pg.streamlit.app （ログイン不要で公開稼働）|
| **Vercel API（FastAPI serverless）** | https://gopipe.vercel.app （`/docs` 公開。`/takeoff` `/estimate` `/application` `/maintenance` `/emergency` `/insulation` `/site_measure` `/riser` `/legend_count`）|
| **Supabase** | Tokyo リージョン。migrations 0001/0002 適用済、**0003 は要 `supabase db push`**。|

- Streamlit は `deploy/vercel-supabase-prep` ブランチ追跡。**自動再デプロイが不安定** → 反映されない時は Streamlit ダッシュボードで手動 **⋮ → Reboot app**。
- Vercel 本番反映は CLI `vercel --prod`（direct push to main はガードでブロック＝PR経由）。
- Vercel Python の要点: `.vercelignore` で `pyproject.toml` を除外し `requirements.txt`（API最小依存）を使わせる。`vercel.json` の `includeFiles` で src/shared/prompts 同梱、出力は read-only FS 回避で `/tmp`。

---

## 6. 宿題（未了 / 主にユーザー側の手作業）

- [ ] **DBパスワードのローテ** — 現行が弱く、スクショで露出済み。要ローテ（service_role は DB-pw 非依存ゆえローテしてもデプロイ無影響）。実値はチャットに貼らない。
- [ ] **migration 0003 適用** — `supabase db push`（学習の堀の永続化に必須）。
- [ ] **Streamlit Secrets に `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` 追加** — Streamlit 上でも学習を永続化するため（app.py の secrets→env 橋渡しは対応済）。Secrets UI で設定、チャットに貼らない。
- [ ] **PR #2（または現ブランチ）を main へマージ** — 直 push はガードでブロック、PR経由。
- [ ] **Streamlit の `ANTHROPIC_API_KEY`** 未設定（実Claudeはローカル/Vercelのみ／mock＋各計算機能はキー無しで公開動作）。
- [ ] 任意: Streamlit サブドメインを `gopipe` に変更し `https://gopipe.streamlit.app` 化。
- [ ] ②段階2 CV（`symbol_match`）とベンチ（`run_benchmark`）は**実図面サンプル**で効果検証が必要。

---

## 7. 次の開発候補（アイデア）

- **入力品質ゲート**の強化: ベクターPDF（CAD出力）優先の導線（精度の主因は入力画質。テキスト層があれば数量が読める）。
- **案件管理 + 成果物ZIP** の拡充（webui にある機能の恒久化）。
- **en 単価の実勢化**・現地法規（ASHRAE/SMACNA）対応（海外Phase1）。
- **マルチテナント/認証・データ居住性**（リージョン分離）— VISION の移植性原則。
- 精度ダッシュボード（`benchmark`/`feedback` の可視化）。

---

## 8. 提案・営業まわりの成果物（gitignore / リポジトリ外）

- 提案デック（ギャラクシー版・全14枚、P.14＝会社概要）: `/Users/ishikawa/gopipe-deck/deck.html` → デスクトップに PDF/PPTX 出力。スキル `and-red-deck`（cinematic.css）ベース。
- ハルキ向け導入提案書 ＋ システム開発委託契約書 ＋ コンサル業務委託契約書（`out/proposal`・`out/contracts`＝gitignore）。
- 送付文面（メール/LINE）ドラフト作成済。会社情報: 株式会社and／代表取締役 石川直輝／〒101-0054 東京都千代田区神田錦町2-7 東和錦町ビル401。

---

## 9. ガードレール（厳守）

- **シークレットをチャット・ログ・コミットに出さない**（APIキー / `sb_secret_*` / DBパスワード / service_role / CRON_SECRET）。露出したら即 revoke → 再設定 → 必要なら git history 洗浄。
- `SUPABASE_SERVICE_ROLE_KEY` は**サーバ側専用**。ブラウザに絶対渡さない。
- 設備図PDF（建物情報を含む）・顧客名をチャットに貼らない。`out/`・`.env*`・`.secrets.local`・`.vercel`・`samples/*.pdf` は gitignore。
- 本番デプロイ・外部送信（メール/公開URL化）は**明示承認**を得てから。
- 新機能追加時は VISION の問い「海外展開を遠ざけていないか」をチェック。

---

## 10. 参照

- [`AGENTS.md`](AGENTS.md) / [`webui/AGENTS.md`](webui/AGENTS.md) — 基本セットアップ
- [`VISION.md`](VISION.md) — 7年後の海外展開ロードマップと移植性設計原則
- `~/.claude/projects/-Users-ishikawa-Documents-Dev-GOPIPE/memory/` — セッション横断メモリ（`gopipe-deployment.md` に本番構成の詳細）
