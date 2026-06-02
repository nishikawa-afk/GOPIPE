#!/usr/bin/env python3
"""GOPIPE 申請ドラフト CLI（F-16）。

拾い出し（run_takeoff）→ 給水装置工事申込書ドラフト（Markdown）を生成する。
口径別延長・衛生器具数は拾い出しから自動集計される。

使い方:
    GOPIPE_LLM_PROVIDER=mock python scripts/run_application.py \
        --input samples/dummy_設備図.pdf --out out/ --project samples/project_info.yaml
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
    p = argparse.ArgumentParser(description="GOPIPE 給水装置工事申込書ドラフト生成")
    p.add_argument("--input", required=True, help="入力 PDF パス（設備図）")
    p.add_argument("--out", default="out/", help="出力ディレクトリ")
    p.add_argument(
        "--project", default="samples/project_info.yaml", help="物件・事業者情報 YAML"
    )
    args = p.parse_args()

    _setup_sys_path()
    try:
        from dotenv import load_dotenv

        load_dotenv(override=True)
    except Exception:
        pass

    from gopipe_takeoff import run_takeoff
    from gopipe_takeoff.application import ProjectInfo, write_application

    root = Path(__file__).resolve().parents[1]
    proj_path = Path(args.project)
    if not proj_path.is_absolute():
        proj_path = root / proj_path
    project = ProjectInfo.from_yaml(proj_path) if proj_path.exists() else ProjectInfo()

    result = run_takeoff(args.input, args.out)
    path = write_application(result.items, project, args.out)

    print(f"✓ 給水装置工事申込書ドラフトを生成: {path}")
    print(f"  （{project.municipality or '汎用様式'} 準拠・提出前に主任技術者の確認が必要）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
