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
    # 高度化: 諸経費内訳の整合・材工合計≒小計・歩掛による総人工
    assert est.site_overhead + est.general_overhead == est.overhead
    assert abs((est.material_total + est.labor_total) - est.subtotal) <= len(est.lines)
    assert est.man_hours > 0  # mock の 大便器/洗面器 に歩掛が付く


def test_application_draft_contains_key_fields(tmp_path):
    """F-16: 申込書ドラフトに口径別延長・器具集計が自動で載る。"""
    from gopipe_takeoff.application import ProjectInfo, build_application_markdown

    result = run_takeoff(str(tmp_path / "dummy.pdf"), str(tmp_path / "out"))
    md = build_application_markdown(result.items, ProjectInfo(municipality="東京都水道局"))

    assert "給水装置工事申込書" in md
    assert "東京都水道局" in md
    assert "合計延長" in md
    assert "DN20" in md  # 給水 VLP DN20 が口径集計される


def test_municipality_template_switches(tmp_path):
    """F-16: 自治体エイリアスで提出先・様式が切り替わり、未登録は default。"""
    from gopipe_takeoff.application import resolve_municipality

    chiba = resolve_municipality("千葉広域水道企業団")
    assert "千葉県企業局" in chiba.get("authority", "")  # 広域企業団→県営水道へ解決

    ichihara = resolve_municipality("市原市")
    assert "市原市" in ichihara.get("authority", "")

    unknown = resolve_municipality("どこかの市")
    assert unknown.get("form_name")  # default が返る（空でない）


def test_emergency_quote_card(tmp_path):
    """F-15: 症状→候補と料金レンジが出て、カードに明朗会計の要素が載る。"""
    from gopipe_takeoff.emergency import Catalog, build_quote_card, diagnose

    catalog = Catalog.from_yaml()
    cands = diagnose("トイレが流れない 水位が上がる", catalog)
    assert len(cands) >= 1
    assert cands[0].job.price_max > 0

    card = build_quote_card("トイレが流れない", cands)
    assert "料金めやす" in card
    assert "作業記録" in card  # 透明性（記録）の担保


def test_maintenance_ledger_and_plan(tmp_path):
    """F-17: 台帳の更新推奨年＝布設年＋耐用年数、プラン推奨が返る。"""
    from gopipe_takeoff.maintenance import build_ledger, load_service_life, recommend_plan

    result = run_takeoff(str(tmp_path / "dummy.pdf"), str(tmp_path / "out"))
    table, plans = load_service_life()
    ledger = build_ledger(result.items, 2008, table)
    assert len(ledger) >= 1

    row = ledger[0]
    assert row.recommend_year == 2008 + row.service_life

    plan = recommend_plan(ledger, plans, current_year=2026)
    assert plan is not None  # 2008布設・2026評価で何らかのプランを推奨
