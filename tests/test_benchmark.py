"""精度ベンチマーク（AI vs 人手）のテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.benchmark import benchmark  # noqa: E402


def test_benchmark_metrics():
    ai = [
        {"name": "仕切弁", "spec": "GV20", "location": "1F", "quantity": 5, "category": "弁類"},
        {"name": "給湯器", "spec": "RUF", "location": "屋外", "quantity": 1, "category": "機器"},
    ]
    truth = [
        {"name": "仕切弁", "spec": "GV20", "location": "1F", "quantity": 6, "category": "弁類"},
        {"name": "給湯器", "spec": "RUF", "location": "屋外", "quantity": 1, "category": "機器"},
        {"name": "ポンプ", "spec": "PU1", "location": "機械室", "quantity": 2, "category": "機器"},
    ]
    r = benchmark(ai, truth)
    assert r.matched == 2
    assert r.precision == 1.0           # AIの2件は両方正解にある
    assert round(r.recall, 2) == 0.67   # 正解3件中2件
    assert r.qty_match == 1             # 給湯器のみ数量一致（仕切弁 5≠6）
    assert [m["name"] for m in r.missing] == ["ポンプ"]
    assert r.extra == []
    assert r.by_category["機器"]["truth"] == 2
    assert "ベンチマーク" in r.format()


def test_quantity_tolerance():
    ai = [{"name": "配管", "spec": "DN20", "location": "1F", "quantity": 100, "category": "給水"}]
    truth = [{"name": "配管", "spec": "DN20", "location": "1F", "quantity": 103, "category": "給水"}]
    # 3% 差は既定許容5%以内 → 数量一致
    assert benchmark(ai, truth).qty_match == 1
    # 厳しめ(2%)なら不一致
    assert benchmark(ai, truth, qty_tol=0.02).qty_match == 0
