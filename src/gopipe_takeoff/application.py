"""F-16: 自治体申請（給水装置工事申込書）ドラフトの自動生成。

拾い出し結果（TakeoffItem）から給水・給湯・排水・通気の口径別延長を自動集計し、
物件・事業者情報（ProjectInfo）と合わせて申込書ドラフト（Markdown）を生成する。

※ 自治体ごとに様式は異なる（東京都水道局／横浜市／大阪広域水道企業団 等で別様式・
   別システム）。本MVPは「共通項目を埋めた汎用ドラフト」を出力し、municipality で
   様式名を切り替える設計。提出前に主任技術者の確認を必須とする。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields
from pathlib import Path

import yaml

from .models import TakeoffItem

# 給水装置（上水系）と排水設備（下水系）の系統区分
WATER_SUPPLY_CATEGORIES = ("給水", "給湯")
DRAINAGE_CATEGORIES = ("排水", "通気")

# 自治体別 様式テンプレ（prompts/municipalities.yaml）
_MUNI_PATH = Path(__file__).resolve().parents[2] / "prompts" / "municipalities.yaml"


def _load_municipalities() -> dict:
    if not _MUNI_PATH.exists():
        return {"municipalities": [], "default": {}}
    with open(_MUNI_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_municipality(name: str, data: dict | None = None) -> dict:
    """自治体名（表記ゆれ・別名含む）から様式テンプレを引く。無ければ default。"""
    data = data if data is not None else _load_municipalities()
    target = (name or "").strip()
    if target:
        for m in data.get("municipalities", []) or []:
            names = [m.get("name", "")] + list(m.get("aliases", []) or [])
            if any(n and (target == n or target in n or n in target) for n in names):
                return m
    return data.get("default", {}) or {}


@dataclass
class ProjectInfo:
    """申請に必要な物件・事業者情報。"""

    project_name: str = ""
    address: str = ""
    owner: str = ""  # 施主・使用者
    contractor_name: str = ""  # 指定給水装置工事事業者名
    contractor_number: str = ""  # 指定番号
    chief_engineer: str = ""  # 給水装置工事主任技術者
    municipality: str = ""  # 提出先自治体（例: 東京都水道局）
    work_type: str = "新設"  # 新設 / 改造 / 撤去 / 修繕

    @classmethod
    def from_yaml(cls, path: str | Path) -> ProjectInfo:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        allowed = {fld.name for fld in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in allowed})


def _caliber(spec: str | None) -> str:
    """spec から口径を DN 表記に正規化する。拾えなければ '口径不明'。"""
    if not spec:
        return "口径不明"
    for pat in (r"DN\s*(\d{1,3})", r"(\d{1,3})\s*mm", r"(\d{1,3})\s*A\b"):
        m = re.search(pat, spec, re.IGNORECASE)
        if m:
            return f"DN{m.group(1)}"
    return "口径不明"


def _pipe_material(spec: str | None) -> str:
    """spec の先頭トークンを管種とみなす（DN/数値トークンは除外）。"""
    if not spec:
        return ""
    head = spec.split()[0]
    if re.match(r"(DN|\d)", head, re.IGNORECASE):
        return ""
    return head


def summarize_pipes(items: list[TakeoffItem], categories: tuple[str, ...]) -> list[dict]:
    """指定系統の (系統, 口径) 別に延長(m)と管種を集計する。"""
    agg: dict[tuple[str, str], dict] = {}
    for it in items:
        if it.category in categories and it.unit == "m":
            key = (it.category, _caliber(it.spec))
            row = agg.setdefault(key, {"system": it.category, "caliber": key[1],
                                       "length": 0.0, "materials": set()})
            row["length"] += it.quantity
            mat = _pipe_material(it.spec)
            if mat:
                row["materials"].add(mat)
    rows = sorted(agg.values(), key=lambda r: (r["system"], r["caliber"]))
    for r in rows:
        r["material"] = "、".join(sorted(r["materials"])) or "—"
    return rows


def summarize_fixtures(items: list[TakeoffItem]) -> list[tuple[str, float]]:
    """衛生器具を名称別に数量集計する。"""
    agg: dict[str, float] = {}
    for it in items:
        if it.category == "衛生器具":
            agg[it.name] = agg.get(it.name, 0.0) + it.quantity
    return sorted(agg.items())


def _num(v: float) -> str:
    """12.0 → '12'、28.5 → '28.5' に整形。"""
    return str(int(v)) if float(v).is_integer() else str(v)


def _pipe_table(rows: list[dict]) -> list[str]:
    if not rows:
        return ["（該当なし）", ""]
    out = ["| 系統 | 口径 | 管種 | 延長(m) |", "| --- | --- | --- | ---: |"]
    for r in rows:
        out.append(f"| {r['system']} | {r['caliber']} | {r['material']} | {_num(r['length'])} |")
    return out


def build_application_markdown(items: list[TakeoffItem], project: ProjectInfo) -> str:
    """給水装置工事申込書ドラフト（Markdown）を組み立てる。"""
    tmpl = resolve_municipality(project.municipality)
    muni = project.municipality or "（汎用様式）"
    form_name = tmpl.get("form_name", "給水装置工事申込書")
    authority = tmpl.get("authority", "（提出先の水道事業者）")
    submit = tmpl.get("submit", "")
    documents = list(tmpl.get("documents", []) or [])
    tmpl_notes = tmpl.get("notes", "")

    supply = summarize_pipes(items, WATER_SUPPLY_CATEGORIES)
    drainage = summarize_pipes(items, DRAINAGE_CATEGORIES)
    fixtures = summarize_fixtures(items)
    supply_total = sum(r["length"] for r in supply)

    L: list[str] = []
    L.append(f"# {form_name}（ドラフト）")
    L.append("")
    L.append(f"> **提出先: {authority}**（{muni}）／ 自動生成ドラフト。"
             f"**提出前に給水装置工事主任技術者が内容を確認・押印すること。**")
    if submit:
        L.append(">")
        L.append(f"> 提出方法: {submit}")
    L.append("")
    L.append("## 1. 申請者・指定事業者")
    L.append("")
    L.append(f"- 指定給水装置工事事業者: **{project.contractor_name or '（記入）'}**"
             f"（指定番号 {project.contractor_number or '（記入）'}）")
    L.append(f"- 給水装置工事主任技術者: **{project.chief_engineer or '（記入）'}**")
    L.append("- 申込年月日: ＿＿＿＿年＿＿月＿＿日（提出時に記入）")
    L.append("")
    L.append("## 2. 工事場所・施主")
    L.append("")
    L.append(f"- 物件名: {project.project_name or '（記入）'}")
    L.append(f"- 工事場所（住所）: {project.address or '（記入）'}")
    L.append(f"- 施主・使用者: {project.owner or '（記入）'}")
    L.append(f"- 工事種別: {project.work_type}")
    L.append("")
    L.append("## 3. 給水装置の概要（給水・給湯／拾い出しから自動集計）")
    L.append("")
    L.extend(_pipe_table(supply))
    L.append("")
    L.append(f"**給水装置 合計延長: {_num(supply_total)} m**")
    L.append("")
    L.append("## 4. 衛生器具（自動集計）")
    L.append("")
    if fixtures:
        L.append("| 器具 | 数量 |")
        L.append("| --- | ---: |")
        for name, qty in fixtures:
            L.append(f"| {name} | {_num(qty)} |")
    else:
        L.append("（該当なし）")
    L.append("")
    L.append("## 5. 参考：排水設備（別途「排水設備計画確認申請」が必要）")
    L.append("")
    L.extend(_pipe_table(drainage))
    L.append("")
    L.append(f"## 6. 提出書類・確認チェックリスト（{muni}）")
    L.append("")
    checklist = documents + [
        "水道メーター口径の確認",
        "給水装置工事主任技術者による数量・口径の確認",
        "施主の同意・押印",
    ]
    for chk in checklist:
        L.append(f"- [ ] {chk}")
    if tmpl_notes:
        L.append("")
        L.append(f"> **{muni} の留意点**: {tmpl_notes}")
    L.append("")
    L.append("---")
    L.append("_本ドラフトは GOPIPE が拾い出しデータから自動生成しました。"
             "口径・延長は図面の信頼度に依存するため、提出前に必ず確認してください。_")
    return "\n".join(L)


def write_application(
    items: list[TakeoffItem], project: ProjectInfo, out_dir: str | Path
) -> Path:
    """申込書ドラフトを Markdown ファイルに書き出す。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "給水装置工事申込書_ドラフト.md"
    path.write_text(build_application_markdown(items, project), encoding="utf-8")
    return path
