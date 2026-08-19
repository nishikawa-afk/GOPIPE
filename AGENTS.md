# AGENTS.md — GOPIPE（配管・設備工事業者向け拾い出しエンジン）

> Codex / Claude などのAIエージェントはまずこのファイルを読むこと。

## プロジェクト概要
- **製品**: 設備図（PDF）→ 配管の管種×口径×延長・継手・バルブ等を抽出 → 系統別拾い出し表（Excel）
- **スタック**: Python 3.11+ / FastAPI / Anthropic Claude / pyproject.toml
- **実プロジェクトパス**: `/Users/ishikawa/Documents/Dev/GOPIPE`
- **ベース**: GOREFORMの拾い出しエンジン（辞書・単価・プロンプト・mockを配管特化に差し替え）

## 対象業種・機能
- **給排水衛生・空調換気・ガス・消火**設備図
- F-12 見積（稼働）: 拾い出し→単価→見積書.xlsx + 材料発注書.xlsx（材工分離）
- F-16 申請（稼働）: 拾い出し→給水装置工事申込書.md（東京都水道局/市原市/千葉県営水道 自治体別様式）
- 単価マスタ: `prompts/unit_prices.yaml`

## セットアップ
```bash
cd /Users/ishikawa/Documents/Dev/GOPIPE
uv sync          # または pip install -r requirements.txt
```

## コマンド
```bash
make run         # API サーバー起動
make test        # テスト
# out/ に生成物が出力される
```

## 設計原則
- **AIは提案・確定は人**（拾い出し数量はAI推定+人間確認）
- mockで一気通貫が稼働（実PDF・API不要でパイプライン検証可）

## 関連
- `GOREFORM` — 母体プロジェクト
- `GOFIRE` — 消防設備向け兄弟プロジェクト

## ガードレール
- APIキーをチャット・ログ・コミットに出さない
- `out/` 生成物はgitignore
