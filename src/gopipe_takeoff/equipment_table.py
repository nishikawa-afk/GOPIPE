"""PDFテキスト層から機器表・数量表・弁リストを抽出（“確定情報”を最優先）。

ベクターPDF(CAD出力)はテキスト層に機器表・台数・型番・口径が「文字」で入って
いるため、画像認識より正確に取得できる。本モジュールはテキスト層の表形式行から
(名称・型番/口径・数量・単位) を取り出す。画像PDFはテキスト層が空のため対象外
（その場合は従来のvision抽出にフォールバック）。
"""
from __future__ import annotations

import re

from .models import TakeoffItem

# 数量＋単位（行末寄りの「2台」「5個」「28.5m」「12 m2」など）
_QTY = re.compile(r"(\d+(?:\.\d+)?)\s*(台|個|箇所|本|枚|式|m2|m²|ｍ2|m|ｍ)(?![0-9A-Za-z])")
# 型番（例: RUF-24A, FCU-2, PU1, VC150）
_MODEL = re.compile(r"([A-Za-z]{1,6}[-‐ー]?\d[\dA-Za-z\-]{0,8})")
# 口径（DN/呼び径/φ/A 表記）
_DIA = re.compile(r"(?:DN|呼び径|φ|Φ)?\s*(\d{2,4})\s*A\b")
_UNIT_NORM = {"m²": "m2", "ｍ2": "m2", "ｍ": "m"}


def _clean(s: str) -> str:
    return s.strip(" 　:：|・,、　").strip()


def extract_from_text(text: str, *, page: int = 1, conf: float = 0.9) -> list[TakeoffItem]:
    """テキスト層の文字列から機器表・数量表の行を拾う。"""
    items: list[TakeoffItem] = []
    for raw in (text or "").splitlines():
        line = _clean(raw)
        if len(line) < 2:
            continue
        m = _QTY.search(line)
        if not m:
            continue
        qty = float(m.group(1))
        unit = _UNIT_NORM.get(m.group(2), m.group(2))
        head = _clean(line[:m.start()])
        if not head:
            continue
        mdl = _MODEL.search(head)
        if mdl:
            spec = mdl.group(1)
        else:
            dm = _DIA.search(head)
            spec = f"{dm.group(1)}A" if dm else None
        items.append(TakeoffItem(page=page, name=head, spec=spec, quantity=qty, unit=unit, confidence=conf))
    return items


def extract_from_pdf(path: str, *, conf: float = 0.9) -> list[TakeoffItem]:
    """PDF各ページのテキスト層から抽出（ベクターPDF向け）。"""
    import fitz  # PyMuPDF

    out: list[TakeoffItem] = []
    doc = fitz.open(path)
    for i, p in enumerate(doc, start=1):
        out.extend(extract_from_text(p.get_text("text") or "", page=i, conf=conf))
    doc.close()
    return out


def has_text_layer(path: str, *, min_chars: int = 50) -> bool:
    """ベクターPDF（テキスト層あり）か簡易判定。"""
    import fitz

    doc = fitz.open(path)
    total = sum(len((p.get_text("text") or "").strip()) for p in doc)
    doc.close()
    return total >= min_chars
