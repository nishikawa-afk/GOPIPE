#!/usr/bin/env python3
"""GOPIPE 予防保全 CLI（F-17）。

拾い出し（run_takeoff）→ 配管台帳（布設年＋耐用年数）→ 更新時期予測 → サブスクプラン提案。

使い方:
    GOPIPE_LLM_PROVIDER=mock python scripts/run_maintenance.py \
        --input samples/dummy_設備図.pdf --out out/ --installed-year 2008
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path


def _setup_sys_path() -> None:
    root = Path(__file__).resolve().parents[1]  # GOPIPE/
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "shared"))


def main() -> int:
    p = argparse.ArgumentParser(description="GOPIPE 予防保全（台帳→更新予測→プラン提案）")
    p.add_argument("--input", required=True, help="入力 PDF パス（設備図）")
    p.add_argument("--out", default="out/", help="出力ディレクトリ")
    p.add_argument("--installed-year", type=int, required=True, help="布設年（西暦、例: 2008）")
    p.add_argument(
        "--current-year", type=int, default=datetime.date.today().year,
        help="評価基準年（既定=今年）",
    )
    p.add_argument("--company", default="", help="会社名（提案書見出しに表示）")
    args = p.parse_args()

    _setup_sys_path()
    try:
        from dotenv import load_dotenv

        load_dotenv(override=True)
    except Exception:
        pass

    from gopipe_takeoff import run_takeoff
    from gopipe_takeoff.maintenance import (
        build_ledger,
        load_service_life,
        recommend_plan,
        write_maintenance,
    )

    result = run_takeoff(args.input, args.out)
    table, plans = load_service_life()
    ledger = build_ledger(result.items, args.installed_year, table)
    plan = recommend_plan(ledger, plans, current_year=args.current_year)
    excel, prop = write_maintenance(
        ledger, plan, plans, args.out,
        installed_year=args.installed_year, current_year=args.current_year, company=args.company,
    )

    n_due = sum(1 for r in ledger if r.remaining(args.current_year) <= 0)
    print(f"✓ 配管台帳 {len(ledger)} 件 ／ 更新時期超過 {n_due} 件 ／ 推奨プラン: {plan.name if plan else '—'}")
    print(f"  配管台帳: {excel}")
    print(f"  提案書  : {prop}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
