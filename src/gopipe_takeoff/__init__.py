"""GOPIPE 拾い出し（積算）エンジン — 配管・設備工事向け。

GOREFORM の拾い出しエンジン（track-a-takeoff）を母体に、給排水衛生・空調・
ガス／消火の設備工事向けへ転用したパッケージ。パイプラインは
`load_pdf → extract → classify → write_excel`（＋bbox があれば marker PDF）。
"""
from __future__ import annotations

from .models import Drawing, DrawingPage, TakeoffItem
from .pipeline import TakeoffPipeline, TakeoffResult, run_takeoff

__all__ = [
    "TakeoffItem",
    "Drawing",
    "DrawingPage",
    "TakeoffPipeline",
    "TakeoffResult",
    "run_takeoff",
]
