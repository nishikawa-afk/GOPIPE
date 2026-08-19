"""縮小されて読めなくなったページを自動でタイル分割する判定のテスト。

実測(2026-08-19 ハルキ実図面): A3 200dpi のスキャンは 1 枚送りだと 112dpi まで落ち、
図面に印刷された吹出口/吸込口表(12行22個)を 1 個も拾えなかった。
3x3 タイル(各300dpi)にすると 12行22個が完全一致した。この切り替えを固定する。
"""

from gopipe_takeoff.pdf_loader import AUTO_TILE_MIN_DPI, auto_grid


def test_十分な解像度なら分割しない():
    assert auto_grid(200) == 1
    assert auto_grid(AUTO_TILE_MIN_DPI) == 1


def test_A3スキャンが112dpiまで落ちたら3分割になる():
    # 実測値。300/112 = 2.68 → 3
    assert auto_grid(112) == 3


def test_呼び出し数の上限を超えない():
    # 2ページなら 2x2=4/ページ（計8回）、3ページ以上は分割しない
    assert auto_grid(112, page_count=2) == 2
    assert auto_grid(112, page_count=3) == 1
    assert auto_grid(112, page_count=10) == 1


def test_ゼロ除算しない():
    assert auto_grid(0) >= 1
