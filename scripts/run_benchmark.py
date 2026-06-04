#!/usr/bin/env python
"""精度ベンチマーク: AI拾い出し vs 人手正解 の一致率を測定する。

使い方:
  # 既存のAI結果JSONと正解CSVを比較
  python scripts/run_benchmark.py --ai out/ai_items.json --truth truth.csv

  # 図面から実抽出して正解と比較（要 .env の ANTHROPIC_API_KEY）
  python scripts/run_benchmark.py --input samples/zumen.pdf --provider claude --truth truth.csv

正解/AIファイル形式:
  - CSV: ヘッダ name,spec,location,quantity,unit,category（1行1品目）
  - JSON: TakeoffItem の配列、または {"items":[...]}
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))


def load_items(path: str) -> list[dict]:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        with open(p, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("items", data) if isinstance(data, dict) else data


def main() -> None:
    ap = argparse.ArgumentParser(description="AI拾い出し vs 人手正解 の精度測定")
    ap.add_argument("--ai", help="AI結果 JSON/CSV")
    ap.add_argument("--input", help="図面PDF（指定すると実抽出して比較）")
    ap.add_argument("--provider", default="mock", help="claude/openai/mock（--input時）")
    ap.add_argument("--truth", required=True, help="人手正解 CSV/JSON")
    ap.add_argument("--tol", type=float, default=0.05, help="数量の相対許容（既定0.05）")
    a = ap.parse_args()

    from gopipe_takeoff.benchmark import benchmark

    if a.input:
        os.environ["GOPIPE_LLM_PROVIDER"] = a.provider
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
        except Exception:
            pass
        from gopipe_takeoff import run_takeoff
        res = run_takeoff(a.input, str(ROOT / "out"))
        ai = [{"category": it.category, "name": it.name, "spec": it.spec, "location": it.location,
               "quantity": it.quantity, "unit": it.unit} for it in res.items]
    elif a.ai:
        ai = load_items(a.ai)
    else:
        ap.error("--ai または --input のどちらかが必要です")

    truth = load_items(a.truth)
    print(benchmark(ai, truth, qty_tol=a.tol).format())


if __name__ == "__main__":
    main()
