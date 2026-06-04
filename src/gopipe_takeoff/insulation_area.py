"""部屋寸法 → 断熱面積（壁/天井/床 m²）→ 拾い出し項目。

寸法の入手元は問わない:
  - iPhone LiDAR アプリ（RoomPlan / Polycam / magicplan）の書き出し
  - 手測り（コンベックス/レーザー距離計）
  - 図面の寸法

断熱は基本「**外皮（外壁・最上階天井 or 屋根・最下階床）**」が対象なので、
壁面積は **外壁の長さ × 階高 − 開口** で出すのが正確（部屋の全周だと内壁を二重に
数えてしまう）。外壁長が不明なときは全周（2×(W+D)）で概算し confidence を下げる。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import TakeoffItem

# 断熱する部位 → 既定の材種カテゴリは classifier 側で付与（name=材種 canonical）。
DEFAULT_SURFACES = ("壁", "天井", "床")


@dataclass
class Room:
    """1 部屋（またはゾーン）の寸法。LiDAR/手測り/図面のどれでも可。"""

    name: str
    width_m: float                       # 幅 W
    depth_m: float                       # 奥行 D
    height_m: float                      # 天井高 H
    openings_m2: float = 0.0             # 窓・ドア等の開口合計（壁から差引）
    exterior_wall_len_m: float | None = None  # 外壁の長さ（不明なら全周で概算）
    surfaces: tuple[str, ...] = DEFAULT_SURFACES
    material: str = "断熱材(グラスウール)"     # dictionary の canonical に合わせる
    thickness_mm: int | None = None


def room_areas(room: Room) -> dict[str, float]:
    """部位ごとの断熱面積 m²。"""
    perim = (
        room.exterior_wall_len_m
        if room.exterior_wall_len_m is not None
        else 2.0 * (room.width_m + room.depth_m)
    )
    wall = max(0.0, perim * room.height_m - room.openings_m2)
    floor = room.width_m * room.depth_m
    areas: dict[str, float] = {}
    if "壁" in room.surfaces:
        areas["壁"] = round(wall, 2)
    if "天井" in room.surfaces:
        areas["天井"] = round(floor, 2)
    if "床" in room.surfaces:
        areas["床"] = round(floor, 2)
    return areas


def to_takeoff_items(rooms: list[Room], *, page: int = 1) -> list[TakeoffItem]:
    """部屋リスト → 断熱の TakeoffItem リスト（部位×部屋ごとに1行・m²）。"""
    items: list[TakeoffItem] = []
    for r in rooms:
        # 外壁長が無く全周概算なら、内壁過大計上の恐れがあるので信頼度を下げる
        approx_wall = r.exterior_wall_len_m is None
        for surface, area in room_areas(r).items():
            conf = 0.95 if not (surface == "壁" and approx_wall) else 0.6
            items.append(
                TakeoffItem(
                    page=page,
                    name=r.material,
                    spec=(f"t{r.thickness_mm}" if r.thickness_mm else None),
                    quantity=area,
                    unit="m2",
                    location=f"{r.name} {surface}",
                    confidence=conf,
                )
            )
    return items


def rooms_from_dicts(data: list[dict]) -> list[Room]:
    """LiDAR アプリ書き出し等の dict 配列 → Room。未知キーは無視。"""
    rooms: list[Room] = []
    for d in data:
        rooms.append(
            Room(
                name=str(d.get("name", "室")),
                width_m=float(d["width_m"]),
                depth_m=float(d["depth_m"]),
                height_m=float(d["height_m"]),
                openings_m2=float(d.get("openings_m2", 0.0) or 0.0),
                exterior_wall_len_m=(
                    float(d["exterior_wall_len_m"])
                    if d.get("exterior_wall_len_m") is not None
                    else None
                ),
                surfaces=tuple(d.get("surfaces", DEFAULT_SURFACES)),
                material=str(d.get("material", "断熱材(グラスウール)")),
                thickness_mm=(int(d["thickness_mm"]) if d.get("thickness_mm") else None),
            )
        )
    return rooms


def load_rooms_json(path: str | Path) -> list[Room]:
    """JSON（部屋寸法の配列）から Room を読む。LiDAR アプリ書き出しの取り込み口。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("rooms", [])
    return rooms_from_dicts(data)
