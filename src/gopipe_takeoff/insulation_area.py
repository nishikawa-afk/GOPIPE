"""部屋寸法/面積 → 断熱面積（壁/天井/床 m²）→ 拾い出し項目。

寸法・面積の入手元は問わない:
  - iPhone LiDAR アプリ（RoomPlan / Polycam / magicplan）の書き出し
    （多くは「床面積」「壁面積」を直接出すので、その値をそのまま使える）
  - 手測り（コンベックス/レーザー距離計）→ 幅×奥行×天井高
  - 図面の寸法

断熱は基本「**外皮（外壁・最上階天井 or 屋根・最下階床）**」が対象。
壁面積の出し方（優先順）:
  1) wall_area_m2 が与えられればそれを使う（LiDAR の実測壁面積）
  2) exterior_wall_len_m（外壁長）× 階高 − 開口
  3) どちらも無ければ全周 2×(W+D) × 階高 − 開口（内壁を二重計上し得るので信頼度↓）
床/天井は floor_area_m2 があればそれ、無ければ W×D。
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .models import TakeoffItem

DEFAULT_SURFACES = ("壁", "天井", "床")


@dataclass
class Room:
    """1 部屋（ゾーン）の寸法 or 面積。寸法と面積はどちらの入力でも可。"""

    name: str
    width_m: float | None = None
    depth_m: float | None = None
    height_m: float | None = None
    floor_area_m2: float | None = None        # 直接指定（LiDAR）。無ければ W×D
    wall_area_m2: float | None = None          # 直接指定（LiDAR）。無ければ外壁長/全周×H−開口
    openings_m2: float = 0.0                    # 窓・ドア等（壁を寸法から出す時のみ差引）
    exterior_wall_len_m: float | None = None    # 外壁の長さ（不明なら全周で概算）
    surfaces: tuple[str, ...] = DEFAULT_SURFACES
    material: str = "断熱材(グラスウール)"          # dictionary の canonical に合わせる
    thickness_mm: int | None = None


def _floor_area(room: Room) -> float:
    if room.floor_area_m2 is not None:
        return room.floor_area_m2
    if room.width_m and room.depth_m:
        return room.width_m * room.depth_m
    return 0.0


def _wall_area(room: Room) -> float:
    if room.wall_area_m2 is not None:
        return room.wall_area_m2
    perim = room.exterior_wall_len_m
    if perim is None and room.width_m and room.depth_m:
        perim = 2.0 * (room.width_m + room.depth_m)
    if perim and room.height_m:
        return max(0.0, perim * room.height_m - room.openings_m2)
    return 0.0


def _wall_is_approx(room: Room) -> bool:
    """外壁長も実測壁面積も無く、全周概算に頼っている＝過大計上の恐れ。"""
    return room.wall_area_m2 is None and room.exterior_wall_len_m is None


def room_areas(room: Room) -> dict[str, float]:
    """部位ごとの断熱面積 m²（surfaces に含まれる部位のみ）。"""
    areas: dict[str, float] = {}
    if "壁" in room.surfaces:
        areas["壁"] = round(_wall_area(room), 2)
    floor = round(_floor_area(room), 2)
    if "天井" in room.surfaces:
        areas["天井"] = floor
    if "床" in room.surfaces:
        areas["床"] = floor
    return areas


def to_takeoff_items(rooms: list[Room], *, page: int = 1) -> list[TakeoffItem]:
    """部屋リスト → 断熱の TakeoffItem リスト（部位×部屋ごとに1行・m²）。"""
    items: list[TakeoffItem] = []
    for r in rooms:
        approx = _wall_is_approx(r)
        for surface, area in room_areas(r).items():
            if area <= 0:
                continue  # 算出できない部位は出さない
            conf = 0.6 if (surface == "壁" and approx) else 0.95
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


# --------------------------------------------------------------------------
# 取り込み口（B）: LiDAR アプリ書き出し / 手入力の dict・JSON・CSV を Room 化
# --------------------------------------------------------------------------
def _num(d: dict, *keys: str) -> float | None:
    """最初に見つかったキーを float で返す（別名・日本語キーに寛容）。"""
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return float(v)
    return None


def rooms_from_dicts(data: list[dict]) -> list[Room]:
    """dict 配列 → Room。未知キーは無視。寸法でも面積直接でも可。"""
    rooms: list[Room] = []
    for d in data:
        surfaces = d.get("surfaces") or DEFAULT_SURFACES
        if isinstance(surfaces, str):
            surfaces = tuple(s.strip() for s in re.split(r"[;|,、]", surfaces) if s.strip())
        th = d.get("thickness_mm") or d.get("厚み")
        rooms.append(
            Room(
                name=str(d.get("name") or d.get("室名") or "室"),
                width_m=_num(d, "width_m", "width", "幅"),
                depth_m=_num(d, "depth_m", "depth", "奥行"),
                height_m=_num(d, "height_m", "height", "天井高", "ceiling_height_m"),
                floor_area_m2=_num(d, "floor_area_m2", "floor_area", "床面積"),
                wall_area_m2=_num(d, "wall_area_m2", "wall_area", "壁面積"),
                openings_m2=_num(d, "openings_m2", "openings", "開口") or 0.0,
                exterior_wall_len_m=_num(d, "exterior_wall_len_m", "exterior_wall_len", "外壁長"),
                surfaces=tuple(surfaces),
                material=str(d.get("material") or d.get("材種") or "断熱材(グラスウール)"),
                thickness_mm=(int(float(th)) if th not in (None, "") else None),
            )
        )
    return rooms


def load_rooms_json(path: str | Path) -> list[Room]:
    """JSON（部屋の配列、または {"rooms":[...]}）から Room を読む。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("rooms", [])
    return rooms_from_dicts(data)


def load_rooms_csv(path: str | Path) -> list[Room]:
    """CSV（1 行 1 部屋・ヘッダ付き）から Room を読む。LiDAR/Excel 書き出しの取り込み口。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return rooms_from_dicts(list(csv.DictReader(f)))
