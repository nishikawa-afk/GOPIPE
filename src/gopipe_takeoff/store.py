"""Supabase 永続化（任意）。

`SUPABASE_URL` と `SUPABASE_SERVICE_ROLE_KEY` が設定されているときだけ有効化される。
PostgREST へ service_role で書き込む（RLS をバイパスするため、このキーは
**サーバ側専用**。クライアント/ブラウザに出さない・リポジトリにコミットしない）。

依存追加なし（標準ライブラリ urllib のみ）＝ Vercel バンドルを増やさない。
認証/テナントは当面 org_slug 指定（将来フロントの Supabase Auth に置換予定）。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .models import TakeoffItem

_TIMEOUT = 15


def _conf() -> tuple[str, str] | None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        return url.rstrip("/"), key
    return None


def is_enabled() -> bool:
    """永続化が設定されているか（env 2 つが揃っているか）。"""
    return _conf() is not None


def _req(method: str, path: str, *, body=None, prefer: str = "", params: str = ""):
    conf = _conf()
    if conf is None:
        raise RuntimeError("Supabase is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)")
    base, key = conf
    url = f"{base}/rest/v1/{path}{params}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            raw = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Supabase {method} {path} -> HTTP {e.code}: {detail}") from None
    return json.loads(raw) if raw else None


def ensure_org(slug: str, name: str) -> str:
    """organizations を slug で upsert し、org_id を返す。"""
    rows = _req(
        "POST", "organizations",
        body=[{"slug": slug, "name": name or slug}],
        prefer="resolution=merge-duplicates,return=representation",
        params="?on_conflict=slug",
    )
    return rows[0]["id"]


def upsert_project(org_id: str, slug: str, title: str, item_count: int) -> str:
    """projects を (org_id, slug) で upsert し、project_id を返す。"""
    rows = _req(
        "POST", "projects",
        body=[{
            "org_id": org_id, "slug": slug, "title": title or slug,
            "status": "takeoff", "item_count": item_count,
        }],
        prefer="resolution=merge-duplicates,return=representation",
        params="?on_conflict=org_id,slug",
    )
    return rows[0]["id"]


def replace_takeoff_items(project_id: str, org_id: str, items: list[TakeoffItem]) -> int:
    """その project の既存 takeoff_items を全削除→再挿入（再拾い出しで上書き）。"""
    _req("DELETE", "takeoff_items", params=f"?project_id=eq.{project_id}")
    if items:
        body = [
            {
                "project_id": project_id, "org_id": org_id,
                "category": it.category, "name": it.name, "spec": it.spec,
                "location": it.location, "quantity": it.quantity,
                "unit": it.unit, "confidence": it.confidence,
            }
            for it in items
        ]
        _req("POST", "takeoff_items", body=body, prefer="return=minimal")
    return len(items)


def persist_takeoff(
    *, org_slug: str, org_name: str, project_slug: str, title: str,
    items: list[TakeoffItem],
) -> dict:
    """org → project → takeoff_items を保存し、id 群と件数を返す。"""
    org_id = ensure_org(org_slug, org_name)
    project_id = upsert_project(org_id, project_slug, title, len(items))
    n = replace_takeoff_items(project_id, org_id, items)
    return {"org_id": org_id, "project_id": project_id, "items": n}
