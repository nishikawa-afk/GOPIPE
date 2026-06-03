"""Vercel Python サーバレス・エントリポイント。

Vercel は api/ 配下の .py をサーバレス関数として検出し、ASGI 変数 `app` を配信する。
ルーティングは FastAPI 側に委譲する（vercel.json の rewrites で全パスをここへ集約）。

ローカルでは従来どおり `uvicorn api.main:app` を使えばよい（この薄いラッパは Vercel 用）。
"""
from __future__ import annotations

import sys
from pathlib import Path

# Vercel 実行環境 (/var/task) でも api.main / src / shared を解決できるよう repo ルートを通す
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.main import app  # noqa: E402  ― Vercel が配信する ASGI アプリ

__all__ = ["app"]
