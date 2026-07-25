"""Supabase 永続化レイヤ（store.py）の単体テスト。

実 Supabase 不要。`_req` をモックして、persist_takeoff が
org→project→items の正しい順序・ペイロードで呼ぶことを固定する。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff import store  # noqa: E402
from gopipe_takeoff.models import TakeoffItem  # noqa: E402


def test_is_enabled_false_without_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert store.is_enabled() is False


def test_is_enabled_true_with_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    assert store.is_enabled() is True


def test_persist_takeoff_builds_expected_calls(monkeypatch):
    calls = []

    def fake_req(method, path, *, body=None, prefer="", params=""):
        calls.append((method, path, body, prefer, params))
        if path == "organizations":
            return [{"id": "org-1"}]
        if path == "projects":
            return [{"id": "proj-1"}]
        return None

    monkeypatch.setattr(store, "_req", fake_req)
    items = [
        TakeoffItem(page=1, name="仕切弁", spec="GV DN20", quantity=5, unit="個",
                    location="1F PS", category="弁類", confidence=0.9),
        TakeoffItem(page=1, name="給水管", spec="VLP DN20", quantity=28.5, unit="m",
                    location="1F 給水系統", category="給水", confidence=0.8),
    ]
    out = store.persist_takeoff(
        org_slug="acme", org_name="ACME", project_slug="p1", title="T", items=items
    )
    assert out["org_id"] == "org-1"
    assert out["project_id"] == "proj-1"
    assert out["drawing_id"] is None
    assert out["items"] == 2

    seq = [(m, p) for (m, p, *_rest) in calls]
    assert ("GET", "organizations") in seq  # 既存会社は引くだけ（会社名を塗り潰さない）
    assert ("POST", "projects") in seq
    # 既存削除 → 再挿入の順
    assert seq.index(("DELETE", "takeoff_items")) < seq.index(("POST", "takeoff_items"))

    # 挿入ペイロードに org_id と quantity が正しく載る（数量はそのまま保持）
    ins = next(c for c in calls if c[0] == "POST" and c[1] == "takeoff_items")
    rows = ins[2]
    assert {r["name"]: r["quantity"] for r in rows} == {"仕切弁": 5, "給水管": 28.5}
    assert all(r["org_id"] == "org-1" and r["project_id"] == "proj-1" for r in rows)


def test_persist_empty_items_never_deletes_existing(monkeypatch):
    """0件のときに既存明細を消さないこと。

    旧仕様は「0件でも DELETE する」だった。AI側の一時障害で0件が返った瞬間に、
    昨日までの拾い出しと、そこに入っていた人の修正が丸ごと消える。
    実際に本番で Anthropic の 500 により0件が返る事象が起きている。
    """
    calls = []

    def fake_req(method, path, *, body=None, prefer="", params=""):
        calls.append((method, path))
        if path == "organizations":
            return [{"id": "org-1"}]
        if path == "projects":
            return [{"id": "proj-1"}]
        return None

    monkeypatch.setattr(store, "_req", fake_req)
    out = store.persist_takeoff(
        org_slug="acme", org_name="ACME", project_slug="p1", title="T", items=[]
    )
    assert out["items"] == 0
    assert ("DELETE", "takeoff_items") not in calls
    assert ("POST", "takeoff_items") not in calls


def test_second_drawing_does_not_wipe_the_first(monkeypatch):
    """2枚目の図面を入れても、1枚目の明細を消さないこと。"""
    deletes = []

    def fake_req(method, path, *, body=None, prefer="", params=""):
        if method == "DELETE":
            deletes.append((path, params))
        if path == "organizations":
            return [{"id": "org-1"}]
        if path == "projects":
            return [{"id": "proj-1"}]
        if path == "drawings":
            return [{"id": "draw-2"}]
        return None

    monkeypatch.setattr(store, "_req", fake_req)
    items = [TakeoffItem(page=1, name="給水管", quantity=10, unit="m", category="給水")]
    out = store.persist_takeoff(
        org_slug="acme", org_name="ACME", project_slug="p1", title="T",
        items=items, source_pdf_path="acme/2枚目.pdf",
    )
    assert out["drawing_id"] == "draw-2"
    # 消すのは「その図面ぶん」だけ。案件まるごとではない。
    assert deletes == [("takeoff_items", "?drawing_id=eq.draw-2")]

def test_ensure_org_does_not_overwrite_existing_name(monkeypatch):
    """既存の会社名を API 呼び出しのたびに slug で塗り潰さないこと。

    upsert にすると画面の会社名が「株式会社ハルキ」→「haruki」に化ける。
    """
    calls = []

    def fake_req(method, path, *, body=None, prefer="", params=""):
        calls.append((method, path, body))
        if method == "GET" and path == "organizations":
            return [{"id": "org-9"}]
        return None

    monkeypatch.setattr(store, "_req", fake_req)
    assert store.ensure_org("haruki", "haruki") == "org-9"
    assert [m for m, _p, _b in calls] == ["GET"]
