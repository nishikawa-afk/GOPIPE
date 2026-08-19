"""Vercel の rewrite で失われる元パスを復元するラッパのテスト。

2026-08-19: Vercel が「rewrite 後のパスでルーティングする」仕様に変わり、
/health も /takeoff もアプリには /api/index として届いて全部 404 になった（本番実測）。
vercel.json の destination に載せた __vpath から元のパスへ戻すのがこのラッパ。
"""

from api.index import _restore_path


def test_元のパスに戻す():
    s = _restore_path({"type": "http", "path": "/api/index", "query_string": b"__vpath=health"})
    assert s["path"] == "/health"
    assert s["query_string"] == b""


def test_ほかのクエリは残す():
    s = _restore_path(
        {"type": "http", "path": "/api/index", "query_string": b"__vpath=takeoff&provider=claude"}
    )
    assert s["path"] == "/takeoff"
    assert s["query_string"] == b"provider=claude"


def test_ルート直下():
    s = _restore_path({"type": "http", "path": "/api/index", "query_string": b"__vpath="})
    assert s["path"] == "/"


def test_vpathが無ければ何もしない():
    orig = {"type": "http", "path": "/health", "query_string": b"a=1"}
    assert _restore_path(orig) == orig
