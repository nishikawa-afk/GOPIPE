"""F-15 透明見積：水まわり緊急修理の「症状 → 標準作業＋明朗料金＋作業記録」。

ぼったくり不信を逆手に取り、「事前に料金レンジを提示し、作業前後の記録を残す」
明朗会計を実現する。symptom テキストを標準作業カタログ
（prompts/emergency_catalog.yaml）とキーワード照合し、料金めやすと作業記録テンプレを
Markdown カードで出力する。LLM 不要で動く（mock の精神）。
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_CATALOG_PATH = Path(__file__).resolve().parents[2] / "prompts" / "emergency_catalog.yaml"
_TAX = 0.10


@dataclass
class StandardJob:
    name: str
    keywords: tuple[str, ...]
    price_min: int
    price_max: int
    work: str = ""
    warranty_months: int = 0

    def price_range_incl_tax(self) -> tuple[int, int]:
        return (round(self.price_min * (1 + _TAX)), round(self.price_max * (1 + _TAX)))


@dataclass
class Candidate:
    job: StandardJob
    score: int


@dataclass
class Catalog:
    jobs: list[StandardJob] = field(default_factory=list)
    fallback: StandardJob | None = None

    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> Catalog:
        path = Path(path) if path else _CATALOG_PATH
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        jobs = [_job(d) for d in (data.get("jobs", []) or [])]
        fb = data.get("fallback")
        return cls(jobs=jobs, fallback=_job(fb) if fb else None)


def _job(d: dict) -> StandardJob:
    return StandardJob(
        name=d.get("name", ""),
        keywords=tuple(d.get("keywords", []) or []),
        price_min=int(d.get("price_min", 0)),
        price_max=int(d.get("price_max", 0)),
        work=d.get("work", ""),
        warranty_months=int(d.get("warranty_months", 0)),
    )


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").replace(" ", "").replace("　", "").lower()


def diagnose(symptom: str, catalog: Catalog, *, top: int = 3) -> list[Candidate]:
    """症状テキストとカタログをキーワード照合し、候補を score（ヒット数）降順で返す。

    何にも当たらなければ fallback（現地調査）を 1 件返す。
    """
    text = _norm(symptom)
    scored: list[Candidate] = []
    for job in catalog.jobs:
        hits = sum(1 for kw in job.keywords if _norm(kw) and _norm(kw) in text)
        if hits > 0:
            scored.append(Candidate(job=job, score=hits))
    scored.sort(key=lambda c: c.score, reverse=True)
    if not scored and catalog.fallback:
        return [Candidate(job=catalog.fallback, score=0)]
    return scored[:top]


def _yen(n: int) -> str:
    return f"¥{n:,}"


def build_quote_card(symptom: str, candidates: list[Candidate], *, company: str = "") -> str:
    """透明見積カード（明朗料金＋作業記録テンプレ）を Markdown で返す。"""
    L: list[str] = []
    L.append(f"# 透明見積カード{('　' + company) if company else ''}")
    L.append("")
    L.append("## ご相談内容")
    L.append(f"> {symptom or '（未入力）'}")
    L.append("")
    L.append("## 想定される作業と料金めやす（税込）")
    L.append("")
    L.append("| 作業 | 料金めやす | 保証 |")
    L.append("| --- | ---: | ---: |")
    for c in candidates:
        lo, hi = c.job.price_range_incl_tax()
        warranty = f"{c.job.warranty_months}ヶ月" if c.job.warranty_months else "—"
        L.append(f"| {c.job.name} | {_yen(lo)}〜{_yen(hi)} | {warranty} |")
    L.append("")
    if candidates and candidates[0].job.work:
        L.append(f"**想定作業の内容**: {candidates[0].job.work}")
        L.append("")
    L.append("> ※ 上記は**事前のめやす**です。正確な金額は現場で部材・状態を確認のうえ確定します。"
             "**見積外の追加作業は、その場で必ず説明し、ご同意をいただいてから**実施します。")
    L.append("")
    L.append("## お客様へのお約束（明朗会計）")
    for promise in (
        "作業前に見積を提示し、ご同意後に着手します",
        "見積にない追加作業は、必ず事前に説明・ご同意をいただきます",
        "作業前後の写真を記録としてお渡しします",
        "出張費・点検費の有無を事前に明示します",
    ):
        L.append(f"- {promise}")
    L.append("")
    L.append("## 作業記録（実施後に記入＝透明性の担保）")
    for label in (
        "実施作業:",
        "使用部材・型番:",
        "作業前写真 / 作業後写真:",
        "実施金額（税込）:",
        "保証期間:",
        "担当者 / 実施日時:",
    ):
        L.append(f"- {label}")
    L.append("")
    L.append("---")
    L.append("_本カードは GOPIPE F-15（透明見積）が生成。事前提示と記録で"
             "「ぼったくり不信」を招かない明朗会計のための雛形です。_")
    return "\n".join(L)
