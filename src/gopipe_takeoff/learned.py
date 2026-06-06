"""学習の堀 — ユーザー修正から『生の名称 → 正規名/カテゴリ/単位』を蓄積し、
次回の分類(classify)に効かせる。使うほど賢くなる顧客辞書。

保存先: ローカルJSON（out/learned_aliases.json）。Supabase が有効なら併せて
永続化（best-effort、未設定でもローカルで機能）。`TakeoffDictionary.add_learned`
で辞書に統合して使う。
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "out" / "learned_aliases.json"


def _norm(s: str | None) -> str:
    return unicodedata.normalize("NFKC", (s or "").strip()).replace(" ", "").replace("　", "")


def load_aliases(path: str | Path = DEFAULT_PATH, *, org: str = "default", remote: bool = True) -> dict:
    """学習済み別名を返す。ローカルJSON ＋（Supabase有効なら）リモートをマージ。

    Supabase 値で上書き（恒久・顧客横断の永続が真の堀）。未設定でもローカルで機能。
    """
    data: dict = {}
    p = Path(path)
    if p.exists():
        try:
            loaded = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:  # noqa: BLE001
            data = {}
    if remote:
        try:
            from . import store
            if store.is_enabled():
                data = {**data, **store.load_learned_aliases(org)}
        except Exception:  # noqa: BLE001
            pass
    return data


def record_alias(
    raw: str, canonical: str, *, category: str | None = None, unit: str | None = None,
    path: str | Path = DEFAULT_PATH, org: str | None = None,
) -> bool:
    """生の名称 raw を正規名 canonical に学習する。変化が無い/空なら False。"""
    raw_n = _norm(raw)
    canon = (canonical or "").strip()
    if not raw_n or not canon or _norm(canon) == raw_n:
        return False
    p = Path(path)
    data = load_aliases(p)
    data[raw_n] = {"canonical": canon, "category": category, "unit": unit, "raw": (raw or "").strip()}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:  # Supabase 併用（任意・best-effort）
        from . import store
        if hasattr(store, "record_learned_alias") and store.is_enabled():
            store.record_learned_alias(org or "default", raw_n, canon, category, unit)
    except Exception:  # noqa: BLE001
        pass
    return True


def stats(aliases: dict | None = None) -> dict:
    a = aliases if aliases is not None else load_aliases()
    return {"total": len(a)}
