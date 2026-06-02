# GOPIPE

配管・設備工事業者向け **拾い出し（積算）エンジン**。給排水衛生・空調換気・ガス／消火の
設備図（PDF）から、配管の管種×口径×延長・継手・バルブ・衛生器具・設備機器・保温などを
抽出し、系統別の拾い出し表（Excel）を生成します。

リフォーム業向け **GOREFORM** の拾い出しエンジン（`track-a-takeoff`）を母体に、
**辞書・単価マスタ・抽出プロンプト・mock を配管特化に差し替え**て転用しています。

| 状態 | 内容 |
| --- | --- |
| **Phase1 拾い出しMVP** | 設備図PDF → 抽出 → 系統別分類 → 拾い出し Excel。**mock で一気通貫が稼働**（API・実PDF不要） |
| 単価マスタ | `prompts/unit_prices.yaml`（系統別カテゴリ単価＋代表器具） |
| **F-12 見積（稼働）** | 拾い出し→単価適用→**見積書.xlsx・材料発注書.xlsx**（材工分離・諸経費・消費税） |
| **F-16 申請（稼働）** | 拾い出し→**給水装置工事申込書ドラフト.md**。東京都水道局／市原市／千葉県営水道（広域企業団）の**自治体別様式**に対応 |
| **F-15 透明見積（稼働）** | 症状→標準作業＋**明朗料金レンジ＋作業記録**カード（`透明見積カード.md`）。ぼったくり不信対策 |
| **F-17 予防保全（稼働）** | 拾い出し＋布設年→**配管台帳＋更新予測＋サブスク提案**（`配管台帳.xlsx`／`予防保全プラン提案.md`） |
| 今後 | 実設備図での精度検証（`PROVIDER=claude`）→ F-15のLLM症状診断・写真対応／F-17のIoT連携／実様式PDF出力 |

## セットアップ

> **Python 3.11 以上が必須**（コードが `str | None` 構文を使うため、3.9 では動きません）。

```bash
# 3.11+ のインタプリタで venv を作成
python3.11 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## 使い方

```bash
# mock で一気通貫（API キー・実 PDF 不要。配管サンプルを返す疎通確認）
make run-takeoff
#   → out/拾い出し表.xlsx が出力される

# 本番（Claude）。設備図 PDF を渡す
make run-takeoff PROVIDER=claude INPUT=samples/あなたの設備図.pdf

# F-12 見積（拾い出し→見積書＋材料発注書）
make run-estimate
#   → out/見積書.xlsx, out/材料発注書.xlsx

# F-16 申請ドラフト（給水装置工事申込書）。物件情報は samples/project_info.yaml
make run-application
#   → out/給水装置工事申込書_ドラフト.md

# F-15 透明見積（症状→明朗料金カード。PDF不要）
make run-emergency SYMPTOM="トイレが流れない"
#   → out/透明見積カード.md

# F-17 予防保全（布設年を指定。配管台帳＋更新予測＋プラン提案）
make run-maintenance YEAR=2008
#   → out/配管台帳.xlsx, out/予防保全プラン提案.md
```

LLM プロバイダは `GOPIPE_LLM_PROVIDER`（`claude` | `openai` | `mock`）で切替。
Claude を使う場合は `.env` に `ANTHROPIC_API_KEY` を設定（`.env.example` 参照）。

### 出力
- `out/拾い出し表.xlsx` … 系統別カテゴリ・管種×口径（仕様）・数量・単位・信頼度＋カテゴリ別集計
- （bbox があれば）`out/AIマーカー付き図面.pdf`

### テスト
```bash
make test   # mock パイプライン＋単価当てのスモークテスト
```

## ディレクトリ

```
GOPIPE/
├── src/gopipe_takeoff/   拾い出しパイプライン（GOREFORM track-a 転用）
│   ├── pipeline.py        load_pdf → extract → classify → write_excel
│   ├── extractor.py       LLM 抽出（prompts/extraction.txt）
│   ├── classifier.py      辞書ベースの系統分類
│   ├── dictionary.py      辞書ローダ＋検証（STANDARD_CATEGORIES=配管系統）
│   ├── pricer.py          単価マスタ（prompts/unit_prices.yaml）
│   ├── excel_writer.py    拾い出し表 Excel 出力
│   └── ...                models / pdf_loader / marker
├── prompts/
│   ├── extraction.txt     配管・設備向け抽出プロンプト
│   ├── dictionary.yaml    配管品目辞書（30品目・系統別）
│   └── unit_prices.yaml   配管単価マスタ
├── shared/                llm_client（claude/openai/mock 切替）, utils
├── scripts/run_takeoff.py CLI
├── samples/               実設備図 PDF を置く場所
└── tests/                 スモークテスト
```

## 配管特化で差し替えた箇所（GOREFORM からの転用）

| 要素 | 内容 |
| --- | --- |
| `prompts/dictionary.yaml` | 内装品目 → **配管30品目**（給水/給湯/排水/通気/消火/ガス/冷媒/ドレン/弁類/継手/衛生器具/機器/ダクト/保温/支持金物/はつり/試験/雑材） |
| `prompts/unit_prices.yaml` | 内装単価 → **配管系統別単価** |
| `prompts/extraction.txt` | 内装抽出 → **設備図抽出**（系統別の管種×口径×延長、立管・隠蔽配管、継手・付帯） |
| `shared/llm_client/mock.py` | 内装サンプル → **給排水＋空調の配管サンプル** |
| `dictionary.py` `STANDARD_CATEGORIES` | 内装カテゴリ → **配管系統カテゴリ** |

母体: `GOREFORM/track-a-takeoff`（要件定義書は `20_Projects/GOPIPE/GOPIPE_要件定義書_v1.1.md`）。
