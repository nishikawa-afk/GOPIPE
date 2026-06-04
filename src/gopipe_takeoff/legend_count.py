"""凡例ドリブン記号カウント — テキスト層ベース（CV前段の段階1）。

ベクターPDFのテキスト層には、凡例表（記号→名称/仕様）と、図面中に配置された
同じ記号コード（多くは SA-1, FCU-2 のように連番付き）が「文字」で入っている。
本モジュールは:
  1. 凡例ブロックを解析して 記号コード → 名称 の対応表を作る（parse_legend）
  2. 図面テキスト中で各コードの出現回数を数える（count_symbols）
     ＝「凡例定義の1回」を差し引いた残り＝図面に配置された個数
  3. TakeoffItem 化（quantity=出現数, spec=コード, name=凡例の名称）

スキャン図（テキスト層なし）には効かない。そこは段階2のCV
（凡例図形のテンプレートマッチ）で補う。本段階はベクター図の個数モノ
（吹出口・吸込口・点検口・弁・器具記号 等）を機械的に数えることが目的。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import TakeoffItem

# 凡例行: 先頭の ASCII 記号コード（英字始まり2〜6字）＋区切り＋日本語を含む説明
_LEGEND_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9]{1,5})[\s:：|｜・,、]+(.+\S)\s*$")
_DN_RE = re.compile(r"^DN\d+$", re.IGNORECASE)
_STOP = {"AND", "NOT", "THE", "FOR", "ALL", "NEW", "OLD", "TOP", "PER", "ROW", "COL", "NO"}


@dataclass
class LegendEntry:
    """凡例の1エントリ（記号コード → 名称）。"""

    code: str
    name: str
    spec: str | None = None
    unit: str = "個"


def _has_cjk(s: str) -> bool:
    """ひらがな/カタカナ/漢字を含むか（凡例の『説明』判定に使う）。"""
    return any(("぀" <= ch <= "ヿ") or ("一" <= ch <= "鿿") for ch in s)


def _code_pattern(code: str) -> re.Pattern[str]:
    """コード本体＋任意の連番（-1 / 2 等）を、英数字境界で1トークンとして数える。"""
    return re.compile(
        rf"(?<![A-Za-z0-9])(?:{re.escape(code)})(?:[-‐]?\d{{1,3}})?(?![A-Za-z0-9])"
    )


def parse_legend(text: str) -> list[LegendEntry]:
    """テキストから凡例エントリ（記号→名称）を抽出。重複コードは先勝ち。"""
    entries: dict[str, LegendEntry] = {}
    for raw in (text or "").splitlines():
        m = _LEGEND_LINE.match(raw)
        if not m:
            continue
        code = m.group(1)
        desc = m.group(2).strip(" 　:：|｜・,、")
        if code.upper() in _STOP or _DN_RE.match(code) or not _has_cjk(desc):
            continue
        entries.setdefault(code, LegendEntry(code=code, name=desc, spec=code))
    return list(entries.values())


def count_symbols(text: str, entries: list[LegendEntry]) -> dict[str, int]:
    """各記号コードの図面配置数。総出現数から凡例定義の1回を差し引く。"""
    out: dict[str, int] = {}
    for e in entries:
        total = len(_code_pattern(e.code).findall(text or ""))
        out[e.code] = max(0, total - 1)
    return out


def items_from_legend(text: str, *, page: int = 1, conf: float = 0.7) -> list[TakeoffItem]:
    """凡例パース＋記号カウント → TakeoffItem（配置数>0 のみ、単位は個）。"""
    entries = parse_legend(text)
    counts = count_symbols(text, entries)
    items: list[TakeoffItem] = []
    for e in entries:
        n = counts.get(e.code, 0)
        if n <= 0:
            continue
        items.append(TakeoffItem(
            page=page, name=e.name, spec=e.spec, quantity=float(n),
            unit=e.unit, confidence=conf, source="legend_count",
        ))
    return items


def count_from_pdf(path: str, *, conf: float = 0.7) -> list[TakeoffItem]:
    """PDF各ページのテキスト層から凡例記号カウント（ベクターPDF向け）。"""
    import fitz  # PyMuPDF

    out: list[TakeoffItem] = []
    doc = fitz.open(path)
    for i, p in enumerate(doc, start=1):
        out.extend(items_from_legend(p.get_text("text") or "", page=i, conf=conf))
    doc.close()
    return out
