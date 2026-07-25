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
import urllib.parse
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
    """organizations を slug で引き、無ければ作って org_id を返す。

    既存の会社名は上書きしない。upsert にすると、API 呼び出しのたびに
    name が slug（例: "haruki"）で塗り潰され、画面に出る会社名が
    「株式会社ハルキ」から崩れてしまうため。
    """
    rows = _req("GET", "organizations", params=f"?slug=eq.{urllib.parse.quote(slug)}&select=id")
    if rows:
        return rows[0]["id"]
    rows = _req(
        "POST", "organizations",
        body=[{"slug": slug, "name": name or slug}],
        prefer="resolution=merge-duplicates,return=representation",
        params="?on_conflict=slug",
    )
    return rows[0]["id"]


def upsert_project(org_id: str, slug: str, title: str, item_count: int,
                   source_pdf_path: str | None = None) -> str:
    """projects を (org_id, slug) で upsert し、project_id を返す。"""
    row = {
        "org_id": org_id, "slug": slug, "title": title or slug,
        "status": "takeoff", "item_count": item_count,
    }
    if source_pdf_path:  # どの図面から起こしたかを案件に残す
        row["source_pdf_path"] = source_pdf_path
    rows = _req(
        "POST", "projects",
        body=[row],
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
    items: list[TakeoffItem], source_pdf_path: str | None = None,
) -> dict:
    """org → project → takeoff_items を保存し、id 群と件数を返す。"""
    org_id = ensure_org(org_slug, org_name)
    project_id = upsert_project(org_id, project_slug, title, len(items), source_pdf_path)
    n = replace_takeoff_items(project_id, org_id, items)
    return {"org_id": org_id, "project_id": project_id, "items": n}


def record_learned_alias(
    org_slug: str, raw: str, canonical: str,
    category: str | None = None, unit: str | None = None, locale: str = "ja",
) -> bool:
    """learned_aliases を (org_id, locale, raw) で upsert（service_role・ロケール別の堀の永続化）。"""
    org_id = ensure_org(org_slug, org_slug)
    _req(
        "POST", "learned_aliases",
        body=[{"org_id": org_id, "raw": raw, "canonical": canonical,
               "category": category, "unit": unit, "locale": locale}],
        prefer="resolution=merge-duplicates,return=minimal",
        params="?on_conflict=org_id,locale,raw",
    )
    return True


def load_learned_aliases(org_slug: str, locale: str = "ja") -> dict:
    """org × locale の learned_aliases を {raw: {canonical, category, unit, raw}} で返す。"""
    org_id = ensure_org(org_slug, org_slug)
    rows = _req(
        "GET", "learned_aliases",
        params=f"?org_id=eq.{org_id}&locale=eq.{locale}&select=raw,canonical,category,unit",
    )
    out: dict = {}
    for r in (rows or []):
        out[r["raw"]] = {
            "canonical": r.get("canonical"), "category": r.get("category"),
            "unit": r.get("unit"), "raw": r.get("raw"),
        }
    return out


def download_drawing(storage_path: str) -> bytes:
    """Storage バケット drawings から設備図PDFを取ってくる（service_role）。

    Vercel のリクエストボディ上限(4.5MB)を避けるため、ブラウザは Storage へ直接
    アップロードし、API にはこのパスだけが渡る。パスの先頭は組織 slug。
    """
    conf = _conf()
    if conf is None:
        raise RuntimeError("Supabase is not configured")
    base, key = conf
    safe = storage_path.lstrip("/")
    if ".." in safe:
        raise RuntimeError("不正なパスです")
    url = f"{base}/storage/v1/object/drawings/{urllib.parse.quote(safe)}"
    req = urllib.request.Request(
        url, method="GET",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"図面の取得に失敗しました (HTTP {e.code}): {detail}") from None
