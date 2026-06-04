"""精度ベンチマーク：AI抽出 vs 人手正解 の一致率を自動測定。

「測って改善する」の中核。AI結果と人手の拾い出し（正解）を突き合わせ、
品目の precision/recall/F1 と、マッチした品目の数量一致率を、全体＆カテゴリ別に出す。
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field


def _n(s) -> str:
    return unicodedata.normalize("NFKC", str(s if s is not None else "")).replace(" ", "").replace("　", "").lower()


def _to_dict(it) -> dict:
    if isinstance(it, dict):
        d = it
    else:  # TakeoffItem 等
        d = {k: getattr(it, k, None) for k in ("category", "name", "spec", "location", "quantity", "unit")}
    return {
        "category": d.get("category"), "name": d.get("name"), "spec": d.get("spec"),
        "location": d.get("location"), "quantity": float(d.get("quantity") or 0), "unit": d.get("unit"),
    }


def _key(d: dict) -> tuple:
    return (_n(d.get("name")), _n(d.get("spec")), _n(d.get("location")))


@dataclass
class BenchResult:
    n_ai: int
    n_truth: int
    matched: int
    precision: float
    recall: float
    f1: float
    qty_match: int
    qty_rate: float
    missing: list = field(default_factory=list)   # 正解にあるがAIに無い
    extra: list = field(default_factory=list)      # AIにあるが正解に無い
    by_category: dict = field(default_factory=dict)

    def format(self) -> str:
        lines = [
            "=== 精度ベンチマーク ===",
            f"品目  : AI {self.n_ai} / 正解 {self.n_truth} / 一致 {self.matched}",
            f"        precision {self.precision:.0%}  recall {self.recall:.0%}  F1 {self.f1:.0%}",
            f"数量  : 一致 {self.qty_match}/{self.matched}（{self.qty_rate:.0%}）",
        ]
        if self.by_category:
            lines.append("カテゴリ別(recall / 数量一致):")
            for c, m in sorted(self.by_category.items()):
                lines.append(f"  {c}: recall {m['recall']:.0%} / qty {m['qty_rate']:.0%}（一致{m['matched']}/{m['truth']}）")
        if self.missing:
            lines.append(f"見落とし {len(self.missing)} 件: " + ", ".join(f"{d['name']}({d.get('spec') or '-'})" for d in self.missing[:10]))
        if self.extra:
            lines.append(f"過剰抽出 {len(self.extra)} 件: " + ", ".join(f"{d['name']}({d.get('spec') or '-'})" for d in self.extra[:10]))
        return "\n".join(lines)


def benchmark(ai_items, truth_items, *, qty_tol: float = 0.05) -> BenchResult:
    """qty_tol: 数量の相対許容（既定 5%）。"""
    ai = [_to_dict(x) for x in ai_items]
    truth = [_to_dict(x) for x in truth_items]
    ai_by = {}
    for d in ai:
        ai_by.setdefault(_key(d), []).append(d)
    truth_by = {}
    for d in truth:
        truth_by.setdefault(_key(d), []).append(d)

    matched = qty_match = 0
    missing, extra = [], []
    bycat: dict = {}

    def cat(d):
        return d.get("category") or "未分類"

    for k, tds in truth_by.items():
        td = tds[0]
        c = cat(td)
        bycat.setdefault(c, {"truth": 0, "matched": 0, "qty": 0})
        bycat[c]["truth"] += 1
        if k in ai_by:
            matched += 1
            bycat[c]["matched"] += 1
            aq, tq = ai_by[k][0]["quantity"], td["quantity"]
            ok = (aq == tq) or (tq != 0 and abs(aq - tq) <= qty_tol * abs(tq))
            if ok:
                qty_match += 1
                bycat[c]["qty"] += 1
        else:
            missing.append(td)
    for k, ads in ai_by.items():
        if k not in truth_by:
            extra.append(ads[0])

    n_ai, n_truth = len(ai), len(truth)
    precision = matched / n_ai if n_ai else 0.0
    recall = matched / n_truth if n_truth else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    qty_rate = qty_match / matched if matched else 0.0
    by_category = {c: {"truth": v["truth"], "matched": v["matched"],
                       "recall": v["matched"] / v["truth"] if v["truth"] else 0.0,
                       "qty_rate": v["qty"] / v["matched"] if v["matched"] else 0.0}
                   for c, v in bycat.items()}
    return BenchResult(n_ai, n_truth, matched, precision, recall, f1, qty_match, qty_rate,
                       missing, extra, by_category)
