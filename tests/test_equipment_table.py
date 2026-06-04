"""機器表テキスト抽出のテスト（テキスト層からの“確定情報”抽出）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.equipment_table import extract_from_text  # noqa: E402


def test_extract_equipment_rows():
    text = "\n".join([
        "機器表",
        "名称 型番 数量",
        "給湯器 RUF-24A 2台",
        "仕切弁 GV 80A 5個",
        "冷温水ポンプ PU-1 3台",
        "保温(GW) t20 28.5m",
        "コア抜き 4箇所",
    ])
    items = extract_from_text(text)
    g = next(it for it in items if "給湯器" in it.name)
    assert g.quantity == 2 and g.unit == "台" and g.spec == "RUF-24A"
    v = next(it for it in items if "仕切弁" in it.name)
    assert v.quantity == 5 and v.unit == "個" and v.spec == "80A"      # 口径フォールバック
    p = next(it for it in items if "ポンプ" in it.name)
    assert p.quantity == 3 and p.unit == "台" and p.spec == "PU-1"
    w = next(it for it in items if "保温" in it.name)
    assert w.quantity == 28.5 and w.unit == "m"
    c = next(it for it in items if "コア抜き" in it.name)
    assert c.quantity == 4 and c.unit == "箇所"
    # 見出し行（数量列に数字なし）は拾わない
    assert all("型番" not in it.name for it in items)
    # テキスト由来は高信頼
    assert all(it.confidence >= 0.9 for it in items)


def test_empty_text():
    assert extract_from_text("") == []
    assert extract_from_text("見出しだけ\nタイトル") == []
