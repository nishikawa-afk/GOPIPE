"""現地実測（LiDAR/巻尺）→ 空調・配管の拾い出し項目。

SiteScape/Polycam 等で測った値（または手測り）を「種別＋寸法/数量」で入れると
TakeoffItem 化する。LiDAR は“3Dメジャー”として使い、本モジュールが数量化を担う。

kind:
  - "角ダクト": width_mm × height_mm × length_m → 展開面積 m²（周長 2(W+H) × 延長）
  - "丸ダクト": dia_mm × length_m            → 展開面積 m²（πD × 延長）
  - "配管"    : (dia_mm or spec) × length_m  → 延長 m
  - "個数"    : count（吹出口/ダンパー/弁 等）→ 個
  - "台数"    : count（室内外機/全熱交/換気扇）→ 台
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from .models import TakeoffItem

UNIT_BY_KIND = {"個数": "個", "台数": "台"}


def _f(d: dict, *keys: str) -> float | None:
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
    return None


def duct_dev_area_m2(
    *, shape: str, width_mm: float | None = None, height_mm: float | None = None,
    dia_mm: float | None = None, length_m: float | None = None,
) -> float:
    """ダクト展開面積 m²。角=2(W+H)×L、丸/スパイラル=πD×L（W/H/D は mm）。"""
    if not length_m or length_m <= 0:
        return 0.0
    if shape.startswith("角") and width_mm and height_mm:
        return round(2.0 * (width_mm + height_mm) / 1000.0 * length_m, 2)
    if (shape.startswith("丸") or "スパイラル" in shape) and dia_mm:
        return round(math.pi * (dia_mm / 1000.0) * length_m, 2)
    return 0.0


def items_from_measures(measures: list[dict], *, page: int = 1) -> list[TakeoffItem]:
    """実測 dict 配列 → TakeoffItem 配列。kind 明示が基本、無ければ寸法から推定。"""
    items: list[TakeoffItem] = []
    for m in measures:
        kind = str(m.get("kind") or "").strip()
        name = str(m.get("name") or "").strip()
        location = str(m.get("location") or m.get("場所") or "").strip()
        spec = m.get("spec") or m.get("仕様") or None
        conf = _f(m, "confidence")
        conf = 0.9 if conf is None else conf  # 実測ベースなので高め
        L = _f(m, "length_m", "length", "延長")
        W = _f(m, "width_mm", "width", "幅")
        H = _f(m, "height_mm", "height", "高さ")
        D = _f(m, "dia_mm", "dia", "口径", "径")
        cnt = _f(m, "count", "quantity", "数量")

        is_duct = kind in ("角ダクト", "丸ダクト") or (not kind and L and (W or D) and cnt is None)
        is_pipe = kind == "配管" or (not kind and L and (D or spec) and not (W or H) and cnt is None)

        if is_duct:
            shape = "角" if (kind == "角ダクト" or (W and H)) else "丸"
            area = duct_dev_area_m2(shape=shape, width_mm=W, height_mm=H, dia_mm=D, length_m=L)
            size = (f"{int(W)}×{int(H)}" if shape == "角" and W and H else (f"φ{int(D)}" if D else ""))
            items.append(TakeoffItem(
                page=page, name=name or "ダクト",
                spec=spec or (f"{size} L{L:g}m" if size else f"L{L:g}m"),
                quantity=area, unit="m2", location=location, confidence=conf,
            ))
        elif is_pipe:
            items.append(TakeoffItem(
                page=page, name=name or "冷温水配管",
                spec=spec or (f"{int(D)}A" if D else None),
                quantity=L or 0.0, unit="m", location=location, confidence=conf,
            ))
        else:
            items.append(TakeoffItem(
                page=page, name=name or "項目", spec=spec,
                quantity=cnt or 0.0, unit=(m.get("unit") or UNIT_BY_KIND.get(kind, "個")),
                location=location, confidence=conf,
            ))
    return items


def load_measures_json(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("measures", []) if isinstance(data, dict) else data


def load_measures_csv(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
