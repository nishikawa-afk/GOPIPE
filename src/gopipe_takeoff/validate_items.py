"""ルールベース整合チェック — 拾い出し項目の怪しい行を機械的にフラグ（精度・信頼性）。

AI/分類の誤りを純ルールで検出してレビューを助ける（即時・無料）。
数量0 / 単位×カテゴリ不一致 / 外れ値 / 重複の疑い を各行の issue リストで返す。
"""
from __future__ import annotations

from .models import TakeoffItem

# 系統別配管（長さ m 想定）
_LEN_CATS = {"給水", "給湯", "排水", "通気", "消火", "ガス", "冷媒", "冷温水", "ドレン", "Piping"}
# 個数・台数で数えるもの
_COUNT_CATS = {"弁類", "継手", "計装", "衛生器具", "機器", "Valve", "Equipment", "HVAC"}
# 面積/長さ（ダクト・保温・断熱）
_AREA_CATS = {"ダクト", "保温", "断熱材", "気密防湿", "Duct", "Insulation"}

_COUNT_UNITS = {"個", "台", "ea", "本", "箇所", "枚", "面"}
_LEN_UNITS = {"m", "ft", "lf"}
_AREA_UNITS = {"m2", "ft2"}
_OUTLIER = 100000.0


def check_item(it: TakeoffItem) -> list[str]:
    """1項目の整合 issue リスト（無ければ空）。"""
    issues: list[str] = []
    cat = (it.category or "").strip()
    unit = (it.unit or "").strip()
    q = it.quantity or 0
    if q == 0:
        issues.append("数量0（未取得）")
    if it.spec and q == 0:
        issues.append("spec有り・数量0")
    if q < 0:
        issues.append("数量がマイナス")
    if q > _OUTLIER:
        issues.append("数量が異常に大きい")
    if cat in _LEN_CATS and unit and unit not in _LEN_UNITS:
        issues.append(f"配管系なのに単位が「{unit}」（m想定）")
    elif cat in _AREA_CATS and unit and unit not in (_AREA_UNITS | _LEN_UNITS):
        issues.append(f"面積/長さ系なのに単位が「{unit}」")
    elif cat in _COUNT_CATS and unit and unit not in _COUNT_UNITS:
        issues.append(f"個数系なのに単位が「{unit}」")
    if not cat or cat == "その他":
        issues.append("未分類（その他）")
    if it.qty_vision is not None and it.qty_vision != q:
        # 機器表を採用した行。図面の読みと食い違ったことを必ず人に見せる。
        issues.append(f"図面と機器表で数量が違う（図面 {_fmt(it.qty_vision)} / 機器表 {_fmt(q)}）")
    return issues


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def check(items: list[TakeoffItem]) -> dict[int, list[str]]:
    """各 index → issue リスト（issue のある行のみ）。重複の疑いも検出。"""
    out: dict[int, list[str]] = {}
    seen: dict[tuple, int] = {}
    # 仕様欄の書き方だけが違う同一品目（例: 図面から「DN20」・機器表から「BV-1」）は
    # 上の key では別物に見えてしまう。数量と単位まで一致する行は二重計上の疑いとして
    # 必ず人に見せる。見積の数量が倍になる事故は、黙って通してはいけない。
    by_qty: dict[tuple, int] = {}
    for i, it in enumerate(items):
        issues = check_item(it)
        key = ((it.name or "").strip(), (it.spec or "").strip(), (it.location or "").strip())
        if any(key):
            if key in seen:
                issues.append(f"重複の疑い（行{seen[key] + 1}と同一）")
            else:
                seen[key] = i
        # 同じ品目・同じ数量でも、階や系統が違えば別物。場所とページまで一致した
        # ときだけ疑う。ここを緩くすると 1F と 2F の弁が真っ赤になり、
        # 本物の二重計上がその中に埋もれて見えなくなる。
        qty_key = (
            (it.name or "").strip(),
            float(it.quantity or 0),
            (it.unit or "").strip(),
            (it.location or "").strip(),
            it.page,
        )
        if qty_key[0] and qty_key[1] > 0:
            if qty_key in by_qty and by_qty[qty_key] != i and not any("重複" in s for s in issues):
                issues.append(f"二重計上の疑い（行{by_qty[qty_key] + 1}と同じ数量）")
            else:
                by_qty.setdefault(qty_key, i)
        if issues:
            out[i] = issues
    return out
