"""学習の堀 — ユーザー修正から『生の名称 → 正規名/カテゴリ/単位』を蓄積し、
次回の分類(classify)に効かせる。使うほど賢くなる顧客辞書。

保存先: ローカルJSON（out/learned_aliases.json）。Supabase が有効なら併せて
永続化（best-effort、未設定でもローカルで機能）。`TakeoffDictionary.add_learned`
で辞書に統合して使う。
"""
from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path

# サーバレス(Vercel)はリポジトリ配下が読取専用。GOPIPE_LEARNED_PATH で /tmp 等へ逃がせる。
# 堀の正本は Supabase 側（learned_aliases）で、このJSONはローカル開発の補助。
DEFAULT_PATH = Path(
    os.environ.get("GOPIPE_LEARNED_PATH")
    or (Path(__file__).resolve().parents[2] / "out" / "learned_aliases.json")
)


def current_org() -> str:
    """いま処理している会社（テナント）の slug。

    堀は会社ごとに育つので、どの会社の辞書を引くかを間違えると
    「使っているのに賢くならない」が静かに起きる。API はリクエストごとに
    GOPIPE_ORG を立てる。
    """
    return os.environ.get("GOPIPE_ORG") or "default"


def _norm(s: str | None) -> str:
    return unicodedata.normalize("NFKC", (s or "").strip()).replace(" ", "").replace("　", "")


def _read(path: str | Path) -> dict:
    """ローカルJSONを生の dict（全ロケールのキー込み）で読む。"""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def load_aliases(path: str | Path | None = None, *, org: str | None = None,
                 locale: str | None = None, remote: bool = True) -> dict:
    """指定ロケールの学習済み別名 {raw: info} を返す。ローカル＋（有効なら）Supabaseをマージ。

    ローカルJSONのキーは `"<locale>/<raw>"`。旧形式の flat キーは ja 既定として扱う。
    Supabase 値で上書き（恒久・顧客横断の永続が真の堀）。未設定でもローカルで機能。
    """
    from .locale import DEFAULT_LOCALE, current_locale

    loc = (locale or current_locale())

    # Supabase が正本のときは、そちらだけを見る。
    # ローカルJSONを混ぜると、サーバレスの /tmp に残った控えが温まった
    # コンテナで生き続け、**取り消したはずの言い換えが効き続ける**。
    # （説明書動画の収録中に実際に踏んだ。取り消しても次の実行でまだ効いていた）
    if remote:
        try:
            from . import store
            if store.is_enabled():
                return store.load_learned_aliases(org or current_org(), locale=loc)
        except Exception:  # noqa: BLE001  読めなければローカルへ落ちる
            pass

    raw = _read(path or DEFAULT_PATH)
    out: dict = {}
    for k, v in raw.items():
        if "/" in k:
            kl, kraw = k.split("/", 1)
            if kl == loc:
                out[kraw] = v
        elif loc == DEFAULT_LOCALE:  # 旧 flat キー = ja
            out[k] = v
    return out


def record_alias(
    raw: str, canonical: str, *, category: str | None = None, unit: str | None = None,
    path: str | Path | None = None, org: str | None = None, locale: str | None = None,
) -> bool:
    """生の名称 raw を正規名 canonical に（ロケール単位で）学習する。変化が無い/空なら False。"""
    from .locale import current_locale

    loc = (locale or current_locale())
    raw_n = _norm(raw)
    canon = (canonical or "").strip()
    if not raw_n or not canon or _norm(canon) == raw_n:
        return False
    p = Path(path or DEFAULT_PATH)
    data = _read(p)
    data[f"{loc}/{raw_n}"] = {
        "canonical": canon, "category": category, "unit": unit,
        "raw": (raw or "").strip(), "locale": loc,
    }
    # ローカルJSONは補助。サーバレスの読取専用FSで落ちても、堀の正本(Supabase)への
    # 書き込みまで道連れにしない（ここで例外を投げると学習が丸ごと消える）。
    wrote_local = False
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        wrote_local = True
    except OSError:
        pass
    persisted = False
    try:  # Supabase 併用（設定時のみ）
        from . import store
        if hasattr(store, "record_learned_alias") and store.is_enabled():
            store.record_learned_alias(org or current_org(), raw_n, canon, category, unit, locale=loc)
            persisted = True
    except Exception:  # noqa: BLE001
        pass
    return wrote_local or persisted


def stats(aliases: dict | None = None) -> dict:
    a = aliases if aliases is not None else load_aliases()
    return {"total": len(a)}
