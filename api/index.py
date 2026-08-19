"""Vercel Python サーバレス・エントリポイント。

Vercel は api/ 配下の .py をサーバレス関数として検出し、ASGI 変数 `app` を配信する。
ルーティングは FastAPI 側に委譲する（vercel.json の rewrites で全パスをここへ集約）。

ローカルでは従来どおり `uvicorn api.main:app` を使えばよい（この薄いラッパは Vercel 用）。

⚠️ 2026-08-19: Vercel の仕様変更で **rewrite 後のパスでルーティングする**ようになった
（ビルドログの警告: "Internal rewrites in backend framework projects now route requests
using the rewritten destination path"）。その結果、`/health` も `/takeoff` も
アプリには `/api/index` として届き、**全エンドポイントが 404** になった（実測）。
対策として rewrite の destination に元のパスを `__vpath` として載せ、
ここで ASGI の scope に戻してから FastAPI に渡す。
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

# Vercel 実行環境 (/var/task) でも api.main / src / shared を解決できるよう repo ルートを通す
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.main import app as _fastapi_app  # noqa: E402

_VPATH = "__vpath"


def _restore_path(scope: dict) -> dict:
    """rewrite で失われた元のパスを `__vpath` から復元する。

    `__vpath` が無いとき（ローカルの uvicorn 等）は何もしない＝従来どおり動く。
    """
    if scope.get("type") not in ("http", "websocket"):
        return scope
    raw_qs = scope.get("query_string") or b""
    if _VPATH.encode() not in raw_qs:
        return scope
    pairs = parse_qsl(raw_qs.decode("latin-1"), keep_blank_values=True)
    vpath = ""
    rest = []
    for k, v in pairs:
        if k == _VPATH and not vpath:
            vpath = v
        else:
            rest.append((k, v))
    if not vpath.startswith("/"):
        vpath = "/" + vpath
    scope = dict(scope)
    scope["path"] = vpath
    scope["raw_path"] = vpath.encode("utf-8")
    scope["query_string"] = urlencode(rest).encode("latin-1")
    return scope


async def app(scope, receive, send):  # noqa: D401 ― Vercel が配信する ASGI アプリ
    await _fastapi_app(_restore_path(scope), receive, send)


__all__ = ["app"]
