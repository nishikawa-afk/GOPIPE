"""API キーゲートの回帰テスト。

本番 API は誰でも叩ける公開エンドポイント。自社の ANTHROPIC_API_KEY を消費する
provider=claude/openai と、service_role で書き込む persist=true は必ず弾くこと。
mock デモは無認証のまま通ること（共有ハブの「触ってみる」導線を殺さないため）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _restore_env():
    before = os.environ.get("GOPIPE_API_KEY")
    yield
    if before is None:
        os.environ.pop("GOPIPE_API_KEY", None)
    else:
        os.environ["GOPIPE_API_KEY"] = before


def test_mock_is_public():
    """mock は無認証で通る（公開デモを壊さない）。"""
    r = client.post("/takeoff", data={"provider": "mock"})
    assert r.status_code == 200
    assert r.json()["count"] > 0


def test_claude_without_key_is_rejected():
    os.environ["GOPIPE_API_KEY"] = "test-key"
    r = client.post("/takeoff", data={"provider": "claude"})
    assert r.status_code == 401


def test_claude_with_wrong_key_is_rejected():
    os.environ["GOPIPE_API_KEY"] = "test-key"
    r = client.post("/takeoff", data={"provider": "claude"}, headers={"x-gopipe-key": "wrong"})
    assert r.status_code == 401


def test_fail_closed_when_server_key_unset():
    """キー未設定は「誰でも通る」ではなく「誰も通れない」に倒す。"""
    os.environ.pop("GOPIPE_API_KEY", None)
    r = client.post("/takeoff", data={"provider": "claude"})
    assert r.status_code == 503


def test_persist_requires_key():
    os.environ["GOPIPE_API_KEY"] = "test-key"
    r = client.post("/takeoff", data={"provider": "mock", "persist": "true"})
    assert r.status_code == 401


@pytest.mark.parametrize("path", ["/estimate", "/application", "/maintenance"])
def test_other_llm_endpoints_are_gated(path: str):
    os.environ["GOPIPE_API_KEY"] = "test-key"
    r = client.post(path, data={"provider": "claude"})
    assert r.status_code == 401


def test_share_and_health_stay_public():
    assert client.get("/health").status_code == 200
    assert client.get("/share").status_code == 200
