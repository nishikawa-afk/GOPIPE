"""ルールベース整合チェックのテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.models import TakeoffItem  # noqa: E402
from gopipe_takeoff.validate_items import check, check_item  # noqa: E402


def test_clean_item_has_no_issues():
    it = TakeoffItem(page=1, name="給水管", spec="DN20", quantity=28.5, unit="m",
                     location="1F", category="給水", confidence=0.9)
    assert check_item(it) == []


def test_unit_category_mismatch():
    it = TakeoffItem(page=1, name="給水管", spec="DN20", quantity=5, unit="個",
                     category="給水", confidence=0.9)
    assert any("配管系" in s for s in check_item(it))


def test_spec_but_zero_quantity_and_unclassified():
    it = TakeoffItem(page=1, name="謎", spec="X-1", quantity=0, unit="台", category="その他")
    issues = check_item(it)
    assert any("数量0" in s for s in issues)
    assert any("未分類" in s for s in issues)


def test_duplicate_detection():
    items = [
        TakeoffItem(page=1, name="仕切弁", spec="GV20", quantity=2, unit="個",
                    location="1F", category="弁類"),
        TakeoffItem(page=1, name="仕切弁", spec="GV20", quantity=3, unit="個",
                    location="1F", category="弁類"),
    ]
    flags = check(items)
    assert 1 in flags and any("重複" in s for s in flags[1])


def test_en_count_unit_ok():
    it = TakeoffItem(page=1, name="Gate Valve", spec="DN50", quantity=6, unit="ea",
                     category="Valve", confidence=0.9)
    assert check_item(it) == []


def test_double_count_across_different_spec_wording():
    """図面からの行と機器表からの行が、仕様欄の書き方違いで二重に残る事故を捕まえる。

    ここを素通りさせると見積の数量が倍になる。数値は直さず、必ず人に見せる。
    """
    from gopipe_takeoff.validate_items import check
    from gopipe_takeoff.models import TakeoffItem

    items = [
        TakeoffItem(page=1, name="給水管", spec="DN20", quantity=28, unit="m", category="給水"),
        TakeoffItem(page=1, name="給水管", spec="GP-1", quantity=28, unit="m", category="給水"),
        TakeoffItem(page=1, name="排水管", spec="DN75", quantity=22, unit="m", category="排水"),
    ]
    flags = check(items)
    assert 1 in flags and any("二重計上" in s for s in flags[1])
    assert 2 not in flags
