"""系統図×階高 → 立管延長/継手/弁 の積算テスト。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.riser_estimate import (  # noqa: E402
    Riser,
    riser_quantities,
    risers_from_dicts,
    to_takeoff_items,
)


def test_riser_length_is_height_times_floors_times_count():
    r = Riser(name="給水立管 PS-1", floors=5, floor_height_m=3.2, count=2,
              fittings_per_floor=2, valves_per_floor=1)
    q = riser_quantities(r)
    assert q["立管"] == round(3.2 * 5 * 2, 2)   # 32.0
    assert q["継手"] == 2 * 5 * 2                # 20
    assert q["弁"] == 1 * 5 * 2                  # 10


def test_branch_run_added_when_given():
    r = Riser(name="PS-2", floors=3, floor_height_m=3.0, branch_per_floor_m=4.0)
    q = riser_quantities(r)
    assert q["立管"] == 9.0
    assert q["横引き"] == 12.0                   # 4.0 × 3 × 1


def test_missing_height_or_floors_yields_zero():
    assert riser_quantities(Riser(name="x", floors=None, floor_height_m=3.0))["立管"] == 0.0
    assert riser_quantities(Riser(name="x", floors=4, floor_height_m=None))["立管"] == 0.0


def test_to_takeoff_items_emits_pipe_and_fittings():
    items = to_takeoff_items([
        Riser(name="給水立管", floors=4, floor_height_m=3.0, count=1, spec="VLP DN20",
              branch_per_floor_m=2.0, fittings_per_floor=2, valves_per_floor=1, material="給水管"),
    ])
    units = {it.unit for it in items}
    assert "m" in units and "個" in units
    pipe = [it for it in items if it.unit == "m" and "立管" in (it.location or "")][0]
    assert pipe.quantity == 12.0 and pipe.name == "給水管"
    fittings = [it for it in items if it.name == "継手"][0]
    assert fittings.quantity == 8        # 2 × 4 × 1


def test_risers_from_dicts_japanese_keys():
    rows = [{"系統名": "排水立管", "階数": 6, "階高": 3.5, "本数": 1,
             "口径": "VP100", "材種": "排水管"}]
    rs = risers_from_dicts(rows)
    assert rs[0].floors == 6 and rs[0].floor_height_m == 3.5
    assert rs[0].material == "排水管" and rs[0].spec == "VP100"
    assert riser_quantities(rs[0])["立管"] == 21.0    # 3.5 × 6
