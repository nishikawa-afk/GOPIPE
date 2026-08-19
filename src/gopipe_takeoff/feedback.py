"""修正キャプチャ：人手の修正を学習データとして蓄積する。

AIの下書きを人が直すたびに (図面参照・AI出力・人手修正) を JSONL に記録。
将来の few-shot / 設備記号検出モデルの fine-tune 用データセットになる（データの堀）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_LOG = Path(os.environ.get("GOPIPE_FEEDBACK_LOG", "out/feedback.jsonl"))


def record_correction(*, project: str, before, after, source: str = "ui",
                      note: str = "", ts: str | None = None,
                      log_path: str | Path | None = None) -> dict:
    """1件の修正を JSONL に追記して返す。

    before/after は dict（または dict 化できる項目）。ts は呼び出し側が文字列で渡す。
    """
    rec = {
        "ts": ts, "project": project, "source": source, "note": note,
        "before": _as_dict(before), "after": _as_dict(after),
    }
    # サーバレス(Vercel)はリポジトリ配下が読取専用。JSONLは fine-tune 用の副産物なので、
    # 書けない環境でもリクエスト自体は落とさない（GOPIPE_FEEDBACK_LOG で /tmp へ逃がせる）。
    p = Path(log_path or DEFAULT_LOG)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        rec = {**rec, "persisted": False}
    return rec


def load_corrections(log_path: str | Path | None = None) -> list[dict]:
    p = Path(log_path or DEFAULT_LOG)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def to_training_pairs(corrections: list[dict]) -> list[dict]:
    """学習用 (入力=AI出力, 正解=人手修正) ペアに整形。"""
    return [{"input": c.get("before"), "label": c.get("after"),
             "project": c.get("project"), "ts": c.get("ts")} for c in corrections]


def stats(corrections: list[dict]) -> dict:
    """蓄積状況の簡易集計。"""
    qty_fixes = sum(1 for c in corrections
                    if (c.get("before") or {}).get("quantity") != (c.get("after") or {}).get("quantity"))
    return {"total": len(corrections), "quantity_fixes": qty_fixes,
            "projects": len({c.get("project") for c in corrections})}


def _as_dict(x) -> dict | None:
    if x is None or isinstance(x, dict):
        return x
    return {k: getattr(x, k, None) for k in ("category", "name", "spec", "location", "quantity", "unit", "confidence")}
