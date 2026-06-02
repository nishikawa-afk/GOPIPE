"""mock パイプラインのスモークテスト（API キー・実 PDF 不要）。

`GOPIPE_LLM_PROVIDER=mock` で run_takeoff が配管項目を返し、系統別カテゴリが
分類され、拾い出し Excel が出力されることを確認する。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

os.environ["GOPIPE_LLM_PROVIDER"] = "mock"

from gopipe_takeoff import run_takeoff  # noqa: E402


def test_mock_pipeline_produces_classified_plumbing_items(tmp_path):
    # 実 PDF は不要。存在しないパスでも mock は配管サンプルを返す。
    result = run_takeoff(str(tmp_path / "dummy.pdf"), str(tmp_path / "out"))

    # 12 件の配管サンプルが拾える
    assert len(result.items) >= 10

    # 系統別カテゴリが分類されている（"その他" に落ちていない）
    cats = {it.category for it in result.items}
    assert "給水" in cats
    assert "排水" in cats
    assert "衛生器具" in cats
    assert "機器" in cats

    # 拾い出し Excel が出力されている
    assert result.excel_path.exists()
    assert result.excel_path.suffix == ".xlsx"


def test_pricer_quotes_each_category(tmp_path):
    """単価マスタが系統別カテゴリに単価を当てられること。"""
    from gopipe_takeoff.pricer import Pricer

    pricer = Pricer.from_yaml(ROOT / "prompts" / "unit_prices.yaml")
    result = run_takeoff(str(tmp_path / "dummy.pdf"), str(tmp_path / "out"))

    quoted = [it for it in result.items if pricer.quote(it) is not None]
    # 全項目に何らかの単価が当たる（カテゴリ・デフォルト含む）
    assert len(quoted) == len(result.items)


def test_estimate_has_positive_total(tmp_path):
    """F-12: 拾い出し → 見積で正の合計（税込）が出て、全項目に単価が当たる。"""
    from gopipe_takeoff.estimate import build_estimate
    from gopipe_takeoff.pricer import Pricer

    pricer = Pricer.from_yaml(ROOT / "prompts" / "unit_prices.yaml")
    result = run_takeoff(str(tmp_path / "dummy.pdf"), str(tmp_path / "out"))
    est = build_estimate(result.items, pricer)

    assert est.subtotal > 0
    assert est.total >= est.subtotal  # 諸経費・消費税が上乗せされる
    assert est.unpriced == []  # 単価未設定が無い


def test_application_draft_contains_key_fields(tmp_path):
    """F-16: 申込書ドラフトに口径別延長・器具集計が自動で載る。"""
    from gopipe_takeoff.application import ProjectInfo, build_application_markdown

    result = run_takeoff(str(tmp_path / "dummy.pdf"), str(tmp_path / "out"))
    md = build_application_markdown(result.items, ProjectInfo(municipality="東京都水道局"))

    assert "給水装置工事申込書" in md
    assert "東京都水道局" in md
    assert "合計延長" in md
    assert "DN20" in md  # 給水 VLP DN20 が口径集計される
