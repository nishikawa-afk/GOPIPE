"""単価マスタ + プライサー (A-08 業者マッチング → 発注書 金額連動).

`prompts/unit_prices.yaml` から単価エントリを読み、
TakeoffItem (+ optional vendor_id) に対して最も specific な単価を引く。

解決ルール:
- 1 つの単価エントリは spec / category / name / vendor_id のうち
  「埋まっているフィールド全て」が item と一致したときマッチ。
- マッチした中から specificity スコアが最大のエントリを採用。
- 同点は yaml で先に書かれた方を優先。

スコア:
    vendor_id: 8, spec: 4, category: 2, name: 1
    (vendor 固有 > spec 固有 > category 固有 > name 部分一致)

エントリ:
    unit_price      - JPY / unit (必須)
    unit            - 何の単位か (例: m2, 本, 式)
    material_ratio  - 0..1。デフォルト 0.5 (材料/施工の按分用)
    notes           - 備考 (任意)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import TakeoffItem


@dataclass(frozen=True)
class PriceEntry:
    """単価エントリ (yaml の 1 行に対応)。"""

    unit_price: float
    unit: str = ""
    material_ratio: float = 0.5
    spec: str | None = None
    category: str | None = None
    name: str | None = None  # 完全一致 (部分一致は今は実装しない)
    vendor_id: str | None = None
    notes: str = ""

    def matches(self, item: TakeoffItem, vendor_id: str | None) -> bool:
        if self.vendor_id and self.vendor_id != vendor_id:
            return False
        if self.spec and self.spec != (item.spec or ""):
            return False
        if self.category and self.category != (item.category or ""):
            return False
        if self.name and self.name != item.name:
            return False
        # 全フィールドが空のエントリは「常にマッチ」だが、specificity 0 で
        # 他があれば負ける。これで「全項目に効くデフォルト」も書ける。
        return True

    @property
    def specificity(self) -> int:
        s = 0
        if self.vendor_id:
            s += 8
        if self.spec:
            s += 4
        if self.category:
            s += 2
        if self.name:
            s += 1
        return s


@dataclass(frozen=True)
class PriceQuote:
    """単価を引いた結果。発注書に渡す。"""

    unit_price: float
    unit: str
    material_ratio: float
    source: str  # どのエントリで引いたか説明 (UI / Excel に出す)
    notes: str = ""

    def total(self, quantity: float) -> float:
        return self.unit_price * quantity

    def material(self, quantity: float) -> float:
        return self.total(quantity) * self.material_ratio

    def labor(self, quantity: float) -> float:
        return self.total(quantity) * (1.0 - self.material_ratio)


@dataclass
class Pricer:
    """単価マスタ。lookup インデックスは持たず、全件 linear scan する。

    現状エントリ数は 100 オーダなので linear scan で十分。
    """

    entries: list[PriceEntry] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def quote(
        self,
        item: TakeoffItem,
        *,
        vendor_id: str | None = None,
    ) -> PriceQuote | None:
        """item に最もマッチするエントリを返す。なければ None。"""
        best: PriceEntry | None = None
        best_score = -1
        for e in self.entries:
            if not e.matches(item, vendor_id):
                continue
            if e.specificity > best_score:
                best = e
                best_score = e.specificity
        if best is None:
            return None
        return PriceQuote(
            unit_price=best.unit_price,
            unit=best.unit or item.unit,
            material_ratio=best.material_ratio,
            source=_describe_entry(best),
            notes=best.notes,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> Pricer:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries: list[PriceEntry] = []
        for row in data.get("prices", []) or []:
            if not isinstance(row, dict):
                continue
            if "unit_price" not in row:
                continue
            try:
                ratio = float(row.get("material_ratio", 0.5))
            except (TypeError, ValueError):
                ratio = 0.5
            entries.append(
                PriceEntry(
                    unit_price=float(row["unit_price"]),
                    unit=str(row.get("unit", "")).strip(),
                    material_ratio=max(0.0, min(1.0, ratio)),
                    spec=_clean_opt(row.get("spec")),
                    category=_clean_opt(row.get("category")),
                    name=_clean_opt(row.get("name")),
                    vendor_id=_clean_opt(row.get("vendor_id")),
                    notes=str(row.get("notes", "")).strip(),
                )
            )
        return cls(entries=entries)


def _clean_opt(v: object) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _describe_entry(e: PriceEntry) -> str:
    parts: list[str] = []
    if e.vendor_id:
        parts.append(f"vendor={e.vendor_id}")
    if e.spec:
        parts.append(f"spec={e.spec}")
    if e.category:
        parts.append(f"cat={e.category}")
    if e.name:
        parts.append(f"name={e.name}")
    if not parts:
        parts.append("デフォルト")
    return ", ".join(parts)
