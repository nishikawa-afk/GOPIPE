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


def test_learn_requires_key():
    os.environ["GOPIPE_API_KEY"] = "test-key"
    r = client.post("/learn", json={"corrections": []})
    assert r.status_code == 401


def test_learn_records_alias_with_key(tmp_path, monkeypatch):
    """名称が変わった行だけが堀（別名）に入る。"""
    os.environ["GOPIPE_API_KEY"] = "test-key"
    monkeypatch.setattr("gopipe_takeoff.learned.DEFAULT_PATH", tmp_path / "learned.json")
    monkeypatch.setattr("gopipe_takeoff.feedback.DEFAULT_LOG", tmp_path / "fb.jsonl")
    r = client.post(
        "/learn",
        headers={"x-gopipe-key": "test-key"},
        json={
            "org_slug": "haruki",
            "corrections": [
                {"before": {"name": "全熱交換ユニット", "unit": "台"},
                 "after": {"name": "全熱交換器", "unit": "台", "category": "機器"}},
                {"before": {"name": "変更なし", "unit": "m"},
                 "after": {"name": "変更なし", "unit": "m"}},
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["captured"] == 2
    assert body["learned"] == 1


def test_export_xlsx_returns_workbook():
    r = client.post(
        "/export/xlsx",
        json={"items": [{"name": "給水管", "quantity": 12.5, "unit": "m", "category": "給水"}]},
    )
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # xlsx = zip


def test_export_xlsx_rejects_empty():
    assert client.post("/export/xlsx", json={"items": []}).status_code == 400


def test_llm_outage_is_reported_in_japanese_not_500(monkeypatch):
    """AI側の一時障害で、現場に英語の500を見せないこと。

    3分待った末に英語のスタックトレースが出ると、担当は理由が分からないまま
    「GoPipeは使えない」と結論する。ページ単位の失敗として日本語で伝える。
    """
    from gopipe_takeoff import extractor

    monkeypatch.setattr(extractor.time, "sleep", lambda *_: None)

    class _Boom:
        def complete(self, *a, **k):
            raise RuntimeError("Error code: 500 - internal server error")

    try:
        extractor._call_llm_for_image(
            _Boom(), "sys", image_png=None, user_text="u", page_number=3
        )
    except extractor.ExtractionFailed as e:
        assert "3ページ" in str(e)
        assert "実行し直して" in str(e)
    else:
        raise AssertionError("ExtractionFailed が投げられていない")


def test_unreadable_page_is_not_reported_as_zero_items():
    """読めなかったページを「0件」に化けさせないこと。"""
    from gopipe_takeoff.extractor import ExtractionFailed, _parse_response

    for raw in ["", "not json at all", '{"a": 1}']:
        try:
            _parse_response(raw, page_number=2)
        except ExtractionFailed:
            pass
        else:
            raise AssertionError(f"黙って0件になった: {raw!r}")
