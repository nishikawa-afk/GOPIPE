"""機器表テキスト抽出の本線統合（reconcile）テスト。

ベクターPDFのテキスト層（機器表）を“確定情報”として vision 抽出に突合し、
数量を上書き・拾い漏れを補完することを検証する。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.extractor import reconcile_with_text_table  # noqa: E402
from gopipe_takeoff.models import TakeoffItem  # noqa: E402


def _v(name, spec, qty, unit="台", conf=0.8):
    return TakeoffItem(page=1, name=name, spec=spec, quantity=qty, unit=unit, confidence=conf)


# 機器表（テキスト層）— 全熱交換器2台 / ポンプ3台 / 仕切弁5個
TEXT = """機器表
全熱交換器 HEX-1 2台
ポンプ PU-1 3台
仕切弁 DN20 5個
"""


def test_reconcile_overwrites_quantity_from_table():
    """vision の数量(1)を機器表の台数(2)で上書きし、信頼度を引き上げる。"""
    vision = [_v("全熱交換器", "HEX-1 250型", 1)]
    out = reconcile_with_text_table(vision, TEXT, page=1)
    hx = next(i for i in out if "全熱交換器" in i.name)
    assert hx.quantity == 2          # 機器表優先（vision 1 → 2）
    assert hx.source == "reconciled"
    assert hx.confidence >= 0.95


def test_reconcile_adds_missing_items():
    """vision に無い機器表項目を拾い漏れとして補完する。"""
    vision = [_v("全熱交換器", "HEX-1", 2)]
    out = reconcile_with_text_table(vision, TEXT, page=1)
    pump = next(i for i in out if "ポンプ" in i.name)
    assert pump.quantity == 3
    assert pump.source == "text_table"


def test_reconcile_spec_substring_match_no_double_count():
    """spec 包含一致（DN20 ⊂ GV DN20）で突合し、二重計上しない。"""
    vision = [_v("仕切弁", "GV DN20", 4, unit="個")]
    out = reconcile_with_text_table(vision, TEXT, page=1)
    gv = [i for i in out if i.name == "仕切弁"]
    assert len(gv) == 1              # 既存項目を更新（重複追加しない）
    assert gv[0].quantity == 5       # 機器表優先（4 → 5）


def test_reconcile_no_text_layer_is_passthrough():
    """テキスト層が無い（画像PDF）なら vision をそのまま返す。"""
    vision = [_v("全熱交換器", "HEX-1", 1)]
    out = reconcile_with_text_table(vision, "", page=1)
    assert len(out) == 1
    assert out[0].quantity == 1
    assert out[0].source is None
