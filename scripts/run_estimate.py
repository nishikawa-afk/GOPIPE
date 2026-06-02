#!/usr/bin/env python3
"""GOPIPE 見積 CLI（F-12）。

拾い出し（run_takeoff）→ 単価マスタ適用 → 見積書＋材料発注書 を一気通貫で生成する。

使い方:
    # mock で一気通貫（API キー・実 PDF 不要）
    GOPIPE_LLM_PROVIDER=mock python scripts/run_estimate.py --input samples/dummy_設備図.pdf --out out/

    # 本番（Claude）。諸経費率や業者単価も指定可
    python scripts/run_estimate.py --input samples/zumen.pdf --out out/ --overhead 0.12 --vendor V001
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _setup_sys_path() -> None:
    root = Path(__file__).resolve().parents[1]  # GOPIPE/
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "shared"))


def main() -> int:
    p = argparse.ArgumentParser(description="GOPIPE 見積（拾い出し→見積書・材料発注書）")
    p.add_argument("--input", required=True, help="入力 PDF パス（設備図）")
    p.add_argument("--out", default="out/", help="出力ディレクトリ")
    p.add_argument("--overhead", type=float, default=0.10, help="諸経費率（既定 0.10）")
    p.add_argument("--vendor", default=None, help="業者ID（vendor 上書き単価を使う場合）")
    args = p.parse_args()

    _setup_sys_path()
    try:
        from dotenv import load_dotenv

        load_dotenv(override=True)
    except Exception:
        pass

    from gopipe_takeoff import run_takeoff
    from gopipe_takeoff.estimate import (
        build_estimate,
        write_estimate_excel,
        write_purchase_order_excel,
    )
    from gopipe_takeoff.pricer import Pricer

    root = Path(__file__).resolve().parents[1]
    out = Path(args.out)

    result = run_takeoff(args.input, args.out)
    pricer = Pricer.from_yaml(root / "prompts" / "unit_prices.yaml")
    est = build_estimate(
        result.items, pricer, overhead_rate=args.overhead, vendor_id=args.vendor
    )
    est_path = write_estimate_excel(est, out / "見積書.xlsx")
    po_path = write_purchase_order_excel(est, out / "材料発注書.xlsx")

    print(f"✓ 見積 {len(est.lines)} 行 / 小計 ¥{est.subtotal:,} → 合計（税込） ¥{est.total:,}")
    if est.unpriced:
        print(f"  ⚠ 単価未設定 {len(est.unpriced)} 行（見積書の備考欄に明示）")
    print(f"  見積書    : {est_path}")
    print(f"  材料発注書: {po_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
