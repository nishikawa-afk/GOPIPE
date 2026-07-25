# AGENTS.md — GOPIPE WebUI（Streamlit 配管拾い出しブラウザUI）

> Codex / Claude などのAIエージェントはまずこのファイルを読むこと。
> GOPIPEプロジェクト全体については `../AGENTS.md` を参照。

## このサブディレクトリの役割
GOPIPE（配管設備工事AI）のブラウザ操作UI。設備図PDFをアップロードして拾い出し → 帳票ダウンロードまでをStreamlitで完結させる。

## スタック
- **UI**: Python Streamlit
- **AI**: Anthropic Claude（プロバイダ切替可: `claude` / `openai`）
- **帳票**: F-12（見積）/ F-15（透明見積）/ F-16（申請）/ F-17（予防保全）
- **実プロジェクトパス**: `/Users/ishikawa/Documents/Dev/GOPIPE/webui`

## 起動方法
```bash
cd /Users/ishikawa/Documents/Dev/GOPIPE
# 仮想環境作成（初回）
python -m venv .venv
# 起動（mockモード: PDF不要でサンプル動作）
.venv/bin/streamlit run webui/app.py
# 本番: LLMプロバイダ=claude + 設備図PDF
```

## 環境変数
```bash
# .env または Streamlit Community Cloud の Secrets
ANTHROPIC_API_KEY=
OPENAI_API_KEY=     # openai プロバイダ選択時
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```
Streamlit Community Cloud では `st.secrets` → `os.environ` に自動ブリッジ済み。

## 設計原則
- **mockモード**: `ANTHROPIC_API_KEY` 未設定でもサンプルデータで動作する
- **「AIは提案・確定は人」**: 拾い出し数量はAI提案。最終確認は施工管理者
- プロバイダは `ANTHROPIC_API_KEY` があれば自動でClaudeを選択

## ガードレール
- APIキーをチャット・ログ・コミットに出さない
- 設備図PDF（建物情報含む）をチャットに貼らない
- Streamlit Community Cloud へのデプロイは明示承認が必要
