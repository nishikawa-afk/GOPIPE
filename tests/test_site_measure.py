"""現地実測モジュール（ダクト展開面積/配管延長/端末数 → 拾い出し）のテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.site_measure import (  # noqa: E402
    duct_dev_area_m2,
    items_from_measures,
    load_measures_csv,
)


def test_duct_area_rect():
    assert duct_dev_area_m2(shape="角", width_mm=500, height_mm=400, length_m=10) == 18.0


def test_duct_area_round():
    assert duct_dev_area_m2(shape="丸", dia_mm=200, length_m=10) == 6.28


def test_items_duct_pipe_count_units():
    items = items_from_measures([
        {"kind": "角ダクト", "name": "角ダクト", "width_mm": 500, "height_mm": 400, "length_m": 10, "location": "1F 天井内"},
        {"kind": "配管", "name": "冷温水配管", "dia_mm": 80, "length_m": 12, "location": "機械室"},
        {"kind": "個数", "name": "吹出口", "count": 8, "location": "1F 事務室"},
        {"kind": "台数", "name": "全熱交換器", "count": 2, "location": "1F"},
    ])
    by = {it.name: it for it in items}
    assert by["角ダクト"].unit == "m2" and by["角ダクト"].quantity == 18.0
    assert by["冷温水配管"].unit == "m" and by["冷温水配管"].quantity == 12.0
    assert by["吹出口"].unit == "個" and by["吹出口"].quantity == 8.0
    assert by["全熱交換器"].unit == "台" and by["全熱交換器"].quantity == 2.0


def test_classify_and_price_site_items():
    from gopipe_takeoff.classifier import classify
    from gopipe_takeoff.dictionary import TakeoffDictionary
    from gopipe_takeoff.pricer import Pricer

    d = TakeoffDictionary.from_yaml(ROOT / "prompts" / "dictionary.yaml")
    p = Pricer.from_yaml(ROOT / "prompts" / "unit_prices.yaml")
    items = classify(items_from_measures([
        {"kind": "角ダクト", "name": "角ダクト", "width_mm": 500, "height_mm": 400, "length_m": 10},
        {"kind": "配管", "name": "冷温水配管", "dia_mm": 80, "length_m": 12},
        {"kind": "台数", "name": "全熱交換器", "count": 2},
    ]), d)
    cats = [it.category for it in items]
    assert "ダクト" in cats     # 角ダクト → ダクト
    assert "冷温水" in cats      # 冷温水配管
    assert "機器" in cats        # 全熱交換器
    assert all(p.quote(it) is not None for it in items)


def test_csv_import(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text(
        "kind,name,width_mm,height_mm,length_m,location\n角ダクト,角ダクト,400,300,8,1F\n",
        encoding="utf-8",
    )
    items = items_from_measures(load_measures_csv(p))
    assert items[0].unit == "m2" and items[0].quantity == round(2 * (400 + 300) / 1000 * 8, 2)
