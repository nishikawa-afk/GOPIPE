#!/usr/bin/env python3
"""GOPIPE 透明見積 CLI（F-15）。

症状テキスト → 標準作業カタログ照合 → 明朗料金＋作業記録の「透明見積カード」を生成。
LLM 不要（キーワード照合）で動く。

使い方:
    python scripts/run_emergency.py --symptom "トイレが流れない 水位が上がる" --out out/
    python scripts/run_emergency.py --symptom "蛇口から水がぽたぽた" --company "○○設備"
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
    p = argparse.ArgumentParser(description="GOPIPE 透明見積（症状→明朗料金カード）")
    p.add_argument("--symptom", required=True, help="症状（例: 'トイレが流れない 水位が上がる'）")
    p.add_argument("--out", default="out/", help="出力ディレクトリ")
    p.add_argument("--company", default="", help="会社名（カード見出しに表示）")
    args = p.parse_args()

    _setup_sys_path()

    from gopipe_takeoff.emergency import Catalog, build_quote_card, diagnose

    catalog = Catalog.from_yaml()
    candidates = diagnose(args.symptom, catalog)
    card = build_quote_card(args.symptom, candidates, company=args.company)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "透明見積カード.md"
    path.write_text(card, encoding="utf-8")

    print(f"✓ 透明見積カードを生成: {path}")
    print("  候補: " + " / ".join(f"{c.job.name}(score={c.score})" for c in candidates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
