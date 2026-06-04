"""断熱面積モジュール（部屋寸法 → 壁/天井/床 m² → 拾い出し）のテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.insulation_area import (  # noqa: E402
    Room,
    room_areas,
    rooms_from_dicts,
    to_takeoff_items,
)


def test_room_areas_with_exterior_wall():
    r = Room("LDK", 4, 5, 2.4, openings_m2=5, exterior_wall_len_m=9)
    a = room_areas(r)
    assert a["壁"] == 16.6   # 9*2.4 - 5
    assert a["天井"] == 20.0
    assert a["床"] == 20.0


def test_room_areas_perimeter_fallback():
    a = room_areas(Room("洋室", 4, 5, 2.4))
    assert a["壁"] == 43.2   # 2*(4+5)*2.4
    assert a["天井"] == 20.0


def test_to_takeoff_items_units_spec_location():
    items = to_takeoff_items([Room("LDK", 4, 5, 2.4, exterior_wall_len_m=9, thickness_mm=90)])
    assert len(items) == 3
    assert all(it.unit == "m2" for it in items)
    assert all(it.spec == "t90" for it in items)
    locs = {it.location for it in items}
    assert {"LDK 壁", "LDK 天井", "LDK 床"} <= locs
    wall = next(it for it in items if it.location == "LDK 壁")
    assert wall.confidence == 0.95   # 外壁長あり → 高信頼


def test_wall_confidence_low_when_perimeter_approx():
    wall = next(it for it in to_takeoff_items([Room("洋室", 4, 5, 2.4)]) if it.location.endswith("壁"))
    assert wall.confidence == 0.6   # 全周概算 → 低信頼（内壁過大計上の恐れ）


def test_classify_and_price_insulation_items():
    from gopipe_takeoff.classifier import classify
    from gopipe_takeoff.dictionary import TakeoffDictionary
    from gopipe_takeoff.pricer import Pricer

    d = TakeoffDictionary.from_yaml(ROOT / "prompts" / "dictionary.yaml")
    p = Pricer.from_yaml(ROOT / "prompts" / "unit_prices.yaml")
    items = classify(to_takeoff_items([Room("LDK", 4, 5, 2.4, exterior_wall_len_m=9)]), d)
    assert all(it.category == "断熱材" for it in items)         # 正しく断熱材に分類
    assert all(p.quote(it) is not None for it in items)        # 全て単価が当たる


def test_rooms_from_dicts_import():
    rooms = rooms_from_dicts([
        {"name": "寝室", "width_m": 3, "depth_m": 4, "height_m": 2.5,
         "material": "硬質ウレタンフォーム", "thickness_mm": 30, "surfaces": ["天井", "床"]},
    ])
    assert rooms[0].name == "寝室" and rooms[0].width_m == 3.0
    items = to_takeoff_items(rooms)
    assert {it.location for it in items} == {"寝室 天井", "寝室 床"}  # 壁は対象外
    assert all(it.name == "硬質ウレタンフォーム" for it in items)
