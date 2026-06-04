"""系統図 × 階高 → 立管・隠蔽配管の延長/継手/弁を積算（図に現れない数量を計算）。

平面図には立管（縦管）の「長さ」が現れない（記号のみ）。系統図から
「何階を貫通する立管が何本あるか」と階高が分かれば、延長(m)・継手(個)・弁(個)を
積算ルールで計算できる。横引き(各階の枝管)・継手数・弁数は階数に比例させる。

入力（Riser）:
  - floors             : 立管が貫通する階数
  - floor_height_m     : 階高 m
  - count              : 立管本数（既定1）
  - branch_per_floor_m : 各階の横引き延長 m（0 なら横引きを出さない）
  - fittings_per_floor : 各階の継手数（既定2: 分岐+曲り）
  - valves_per_floor   : 各階の弁数（既定0）

計算:
  立管延長 = floor_height_m × floors × count
  横引延長 = branch_per_floor_m × floors × count
  継手     = fittings_per_floor × floors × count
  弁       = valves_per_floor × floors × count
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .models import TakeoffItem


@dataclass
class Riser:
    """1 系統の立管（縦管）。系統図＋階高から延長/継手/弁を積算する。"""

    name: str                                   # 例: 給水立管 PS-1
    floors: int | None = None                   # 貫通階数
    floor_height_m: float | None = None         # 階高 m
    count: int = 1                              # 立管本数
    spec: str | None = None                     # 口径/材種仕様
    material: str = "配管"                       # dictionary canonical に寄せる
    branch_per_floor_m: float = 0.0             # 各階の横引き延長 m
    fittings_per_floor: float = 2.0             # 各階の継手数（分岐+曲り）
    valves_per_floor: float = 0.0               # 各階の弁数
    location: str | None = None


def riser_quantities(r: Riser) -> dict[str, float]:
    """立管系統の数量（立管m / 横引きm / 継手個 / 弁個）。算出不能は0。"""
    if not r.floors or not r.floor_height_m or r.floors <= 0 or r.floor_height_m <= 0:
        return {"立管": 0.0, "横引き": 0.0, "継手": 0.0, "弁": 0.0}
    span = r.floors * max(1, r.count)
    return {
        "立管": round(r.floor_height_m * span, 2),
        "横引き": round(r.branch_per_floor_m * span, 2),
        "継手": float(round(r.fittings_per_floor * span)),
        "弁": float(round(r.valves_per_floor * span)),
    }


def to_takeoff_items(risers: list[Riser], *, page: int = 1) -> list[TakeoffItem]:
    """立管リスト → TakeoffItem（立管m・横引きm・継手個・弁個。0は出さない）。"""
    items: list[TakeoffItem] = []
    for r in risers:
        q = riser_quantities(r)
        loc = r.location or r.name
        if q["立管"] > 0:
            items.append(TakeoffItem(
                page=page, name=r.material, spec=r.spec, quantity=q["立管"],
                unit="m", location=f"{loc} 立管", confidence=0.8,
            ))
        if q["横引き"] > 0:
            items.append(TakeoffItem(
                page=page, name=r.material, spec=r.spec, quantity=q["横引き"],
                unit="m", location=f"{loc} 横引き", confidence=0.75,
            ))
        if q["継手"] > 0:
            items.append(TakeoffItem(
                page=page, name="継手", spec=r.spec, quantity=q["継手"],
                unit="個", location=loc, confidence=0.7,
            ))
        if q["弁"] > 0:
            items.append(TakeoffItem(
                page=page, name="仕切弁", spec=r.spec, quantity=q["弁"],
                unit="個", location=loc, confidence=0.75,
            ))
    return items


# ---- 取り込み口: dict / JSON / CSV（別名・日本語キーに寛容）----
def _f(d: dict, *keys: str) -> float | None:
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
    return None


def risers_from_dicts(data: list[dict]) -> list[Riser]:
    """dict 配列 → Riser。別名・日本語キーに寛容。"""
    out: list[Riser] = []
    for d in data:
        floors = _f(d, "floors", "階数", "貫通階数")
        cnt = _f(d, "count", "本数")
        fpf = _f(d, "fittings_per_floor", "継手数")
        vpf = _f(d, "valves_per_floor", "弁数")
        out.append(Riser(
            name=str(d.get("name") or d.get("系統") or d.get("系統名") or "立管"),
            floors=(int(floors) if floors else None),
            floor_height_m=_f(d, "floor_height_m", "floor_height", "階高"),
            count=(int(cnt) if cnt else 1),
            spec=d.get("spec") or d.get("仕様") or d.get("口径") or None,
            material=str(d.get("material") or d.get("材種") or "配管"),
            branch_per_floor_m=_f(d, "branch_per_floor_m", "branch_per_floor", "横引き") or 0.0,
            fittings_per_floor=(fpf if fpf is not None else 2.0),
            valves_per_floor=(vpf if vpf is not None else 0.0),
            location=d.get("location") or d.get("場所") or None,
        ))
    return out


def load_risers_json(path: str | Path) -> list[Riser]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("risers", [])
    return risers_from_dicts(data)


def load_risers_csv(path: str | Path) -> list[Riser]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return risers_from_dicts(list(csv.DictReader(f)))
