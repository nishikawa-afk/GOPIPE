"""ロケール分離（海外展開の土台 / VISION.md）のテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff import locale  # noqa: E402
from gopipe_takeoff.classifier import classify  # noqa: E402
from gopipe_takeoff.dictionary import TakeoffDictionary  # noqa: E402
from gopipe_takeoff.models import TakeoffItem  # noqa: E402
from gopipe_takeoff.pricer import Pricer  # noqa: E402


def test_resolve_prefers_locale_dir():
    p = locale.resolve("dictionary.yaml", locale="en")
    assert p.parent.name == "en" and p.exists()


def test_resolve_falls_back_to_flat_ja():
    # extraction.txt は flat のみ → en でも flat(ja既定) にフォールバック
    p = locale.resolve("extraction.txt", locale="en")
    assert p.exists() and p.parent.name == "prompts"


def test_default_locale_is_ja(monkeypatch):
    monkeypatch.delenv("GOPIPE_LOCALE", raising=False)
    assert locale.current_locale() == "ja"
    assert locale.resolve("dictionary.yaml").parent.name == "prompts"  # flat = ja既定


def test_available_locales_has_ja_and_en():
    locs = locale.available_locales()
    assert "ja" in locs and "en" in locs


def test_money_for_currency():
    assert locale.money_for("ja")["symbol"] == "¥"
    m = locale.money_for("en")
    assert m["symbol"] == "$" and m["code"] == "USD"


def test_en_knowledge_valid_and_usable():
    d = TakeoffDictionary.from_yaml(locale.resolve("dictionary.yaml", locale="en"))
    pr = Pricer.from_yaml(locale.resolve("unit_prices.yaml", locale="en"))
    out = classify([TakeoffItem(page=1, name="Supply Air Diffuser", quantity=4, unit="ea")], d)
    assert out[0].category == "HVAC" and out[0].name == "Supply Air Diffuser"
    assert pr.quote(out[0]) is not None
