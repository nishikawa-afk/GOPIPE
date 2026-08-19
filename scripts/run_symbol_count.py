#!/usr/bin/env python
"""凡例ドリブン記号カウント・段階2（CVテンプレートマッチ）のローカル実行CLI。

スキャン図（テキスト層なし）でも、凡例の記号画像（テンプレート）を図面上で
テンプレートマッチして個数を数える。opencv があれば高速・大判対応、無ければ
numpy フォールバック（小さめ画像向け）。

準備:
  pip install opencv-python-headless        # 推奨（大判図面で必須級）
  # 凡例から記号を1つずつ切り出した PNG を用意（例: SA.png, EA.png ...）

使い方:
  # PDFの1ページを画像化して、テンプレート群をカウント
  python scripts/run_symbol_count.py --pdf 図面.pdf --page 1 --dpi 200 \
      --template SA.png --template EA.png --threshold 0.8

  # すでに画像化済みのページに対して
  python scripts/run_symbol_count.py --image page1.png --template SA.png --threshold 0.82
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))


def main() -> None:
    ap = argparse.ArgumentParser(description="記号テンプレートマッチでの個数カウント（CV段階2）")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", help="図面PDF（--page でページ指定）")
    src.add_argument("--image", help="図面画像（PNG/JPG）")
    ap.add_argument("--page", type=int, default=1, help="PDFのページ番号（1始まり）")
    ap.add_argument("--dpi", type=int, default=200, help="PDF画像化のDPI（既定200。スキャンは高めが有利）")
    ap.add_argument("--template", action="append", required=True, help="記号テンプレ画像（複数可）")
    ap.add_argument("--threshold", type=float, default=0.8, help="一致しきい値（0..1, 既定0.8）")
    ap.add_argument("--scales", default="1.0", help="探索スケール（カンマ区切り。例 0.8,1.0,1.2）")
    a = ap.parse_args()

    import numpy as np
    from PIL import Image

    from gopipe_takeoff.symbol_match import count_matches, cv2, page_image

    print("opencv:", "あり（高速）" if cv2 is not None else "なし（numpyフォールバック）")

    if a.pdf:
        img = page_image(a.pdf, page_index=a.page - 1, dpi=a.dpi)
    else:
        img = np.asarray(Image.open(a.image))

    scales = tuple(float(s) for s in a.scales.split(",") if s.strip())
    total = 0
    print(f"=== 記号カウント（threshold={a.threshold}, scales={scales}）===")
    for tpath in a.template:
        tpl = np.asarray(Image.open(tpath))
        n = count_matches(img, tpl, threshold=a.threshold, scales=scales)
        total += n
        print(f"  {Path(tpath).stem}: {n} 個")
    print(f"合計: {total} 個")


if __name__ == "__main__":
    main()
