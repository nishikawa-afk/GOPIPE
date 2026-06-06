"""ロケール対応の知識ファイル解決（海外展開の土台 / VISION.md）。

知識レイヤー（dictionary / unit_prices / extraction 等）を国コードで切り替える。
解決順:
  1) prompts/{locale}/{name}
  2) prompts/{name}        ← flat = ja 既定の既存資産（後方互換）
  3) prompts/ja/{name}
既存の flat ファイルはそのまま ja として機能する。`GOPIPE_LOCALE` で切替（既定 ja）。
"""
from __future__ import annotations

import os
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
DEFAULT_LOCALE = "ja"


def current_locale() -> str:
    return (os.environ.get("GOPIPE_LOCALE") or DEFAULT_LOCALE).strip().lower() or DEFAULT_LOCALE


def resolve(name: str, locale: str | None = None) -> Path:
    """知識ファイル name を locale 優先で解決して Path を返す。"""
    loc = (locale or current_locale()).strip().lower()
    for cand in (
        PROMPTS_DIR / loc / name,
        PROMPTS_DIR / name,
        PROMPTS_DIR / DEFAULT_LOCALE / name,
    ):
        if cand.exists():
            return cand
    return PROMPTS_DIR / name  # 無ければ flat パス（呼び出し側でエラーになる）


def available_locales() -> list[str]:
    """利用可能なロケール（ja＋prompts配下の非空サブフォルダ）。"""
    locs = {DEFAULT_LOCALE}
    if PROMPTS_DIR.exists():
        for p in PROMPTS_DIR.iterdir():
            if p.is_dir() and any(p.iterdir()):
                locs.add(p.name.lower())
    return sorted(locs)
