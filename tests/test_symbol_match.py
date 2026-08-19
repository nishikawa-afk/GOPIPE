"""記号テンプレートマッチング（CV・段階2, numpy NCC）のテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.symbol_match import count_matches, find_matches  # noqa: E402


def _plus(size: int = 9) -> np.ndarray:
    """十字（プラス）記号テンプレート。"""
    t = np.zeros((size, size), float)
    c = size // 2
    t[c - 1:c + 2, :] = 255.0
    t[:, c - 1:c + 2] = 255.0
    return t


def _canvas(template, positions, shape=(90, 200)) -> np.ndarray:
    img = np.zeros(shape, float)
    h, w = template.shape
    for (y, x) in positions:
        img[y:y + h, x:x + w] = template
    return img


def test_find_matches_counts_distinct_symbols():
    t = _plus(9)
    pos = [(10, 10), (10, 70), (10, 140), (50, 40)]
    matches = find_matches(_canvas(t, pos), t, threshold=0.9)
    assert len(matches) == 4                     # NMS で各記号は1件に集約
    assert all(m.score > 0.99 for m in matches)  # 完全一致位置は NCC≈1.0


def test_count_matches_equals_placed():
    t = _plus(9)
    assert count_matches(_canvas(t, [(10, 10), (40, 90)]), t, threshold=0.9) == 2


def test_blank_image_returns_zero():
    t = _plus(9)
    assert count_matches(np.zeros((60, 60), float), t, threshold=0.9) == 0
