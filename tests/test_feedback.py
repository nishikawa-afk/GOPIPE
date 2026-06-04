"""修正キャプチャ（学習データ蓄積）のテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.feedback import (  # noqa: E402
    load_corrections,
    record_correction,
    stats,
    to_training_pairs,
)


def test_record_load_stats(tmp_path):
    p = tmp_path / "fb.jsonl"
    record_correction(project="P", before={"name": "ダクト", "quantity": 0},
                      after={"name": "ダクト", "quantity": 18}, ts="2026-06-04", log_path=p)
    record_correction(project="P", before={"name": "仕切弁", "quantity": 2},
                      after={"name": "仕切弁", "quantity": 2, "spec": "GV20"}, ts="2026-06-04", log_path=p)
    items = load_corrections(p)
    assert len(items) == 2 and items[0]["project"] == "P"
    s = stats(items)
    assert s["total"] == 2 and s["quantity_fixes"] == 1 and s["projects"] == 1
    pairs = to_training_pairs(items)
    assert pairs[0]["label"]["quantity"] == 18 and pairs[0]["input"]["quantity"] == 0


def test_load_missing_returns_empty(tmp_path):
    assert load_corrections(tmp_path / "none.jsonl") == []
