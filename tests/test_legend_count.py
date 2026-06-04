"""凡例ドリブン記号カウント（テキスト層ベース）のテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.legend_count import (  # noqa: E402
    count_symbols,
    items_from_legend,
    parse_legend,
)

# 凡例（記号→名称）＋ 図面に配置された記号（連番付き）。VAV は凡例のみ＝未配置。
TEXT = """凡例
SA 給気口
EA 排気口
FCU ファンコイルユニット
VAV 可変風量ユニット
1階平面図
SA-1 SA-2 SA-3
EA-1 EA-2
FCU-1 FCU-2 FCU-3 FCU-4
"""


def test_parse_legend_maps_codes_to_names():
    codes = {e.code: e.name for e in parse_legend(TEXT)}
    assert codes["SA"] == "給気口"
    assert codes["FCU"] == "ファンコイルユニット"
    assert "VAV" in codes                 # 凡例には載る（配置数は別）


def test_count_symbols_counts_placed_instances():
    entries = parse_legend(TEXT)
    counts = count_symbols(TEXT, entries)
    assert counts["SA"] == 3              # SA-1,2,3（凡例定義の1回は差引）
    assert counts["EA"] == 2
    assert counts["FCU"] == 4
    assert counts["VAV"] == 0             # 凡例のみ＝図面未配置


def test_items_from_legend_skips_zero_and_sets_source():
    by = {it.spec: it for it in items_from_legend(TEXT)}   # spec == code
    assert by["SA"].quantity == 3 and by["SA"].name == "給気口" and by["SA"].unit == "個"
    assert by["SA"].source == "legend_count"
    assert "VAV" not in by                # 配置数0は出さない


def test_no_legend_returns_empty():
    assert items_from_legend("ただの図面テキスト\n寸法 1000\n外壁 RC造\n") == []
