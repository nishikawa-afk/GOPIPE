"""GOPIPE REST API（FastAPI）。

既存の拾い出し／見積／申請／予防保全／透明見積エンジンを Web（Next.js）や
他クライアントから叩けるよう REST 化する。エンジンは src/gopipe_takeoff を直接 import。

起動:
    .venv/bin/uvicorn api.main:app --reload --port 8000
    （mock は file 無しでサンプルが返る。本番は provider=claude＋PDF）
"""
from __future__ import annotations

import datetime
import hmac
import os
import sys
import tempfile
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "src", ROOT / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gopipe_takeoff.locale import resolve as _kpath  # noqa: E402

# Vercel 等サーバレスは /tmp 以外が読取専用。出力 xlsx は応答に含めない副産物なので
# 書込可能な一時ディレクトリへ逃がす（run_takeoff が out_dir を mkdir する）。
OUT = Path(tempfile.gettempdir()) / "gopipe_out"

app = FastAPI(title="GOPIPE API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番では Vercel ドメインに絞る
    allow_methods=["*"],
    allow_headers=["*"],
)


def _save_upload(file: UploadFile | None) -> Path:
    """アップロードPDFを一時保存。無ければ mock 用ダミーパスを返す。"""
    if file is None:
        return ROOT / "samples" / "dummy_設備図.pdf"
    tmp = Path(tempfile.gettempdir()) / (file.filename or "upload.pdf")
    tmp.write_bytes(file.file.read())
    return tmp


def _items_json(items) -> list[dict]:
    return [
        {
            "category": it.category, "name": it.name, "spec": it.spec,
            "location": it.location, "quantity": it.quantity, "unit": it.unit,
            "confidence": round(it.confidence, 2),
        }
        for it in items
    ]


# 無認証で開放してよいプロバイダ（自社の LLM キーを消費しない＝課金されない）。
# claude / openai は ANTHROPIC_API_KEY 等を消費するので、必ずキーゲートを通す。
_FREE_PROVIDERS = {"", "mock"}


def _require_key(api_key: str | None, what: str) -> None:
    """課金・書き込みを伴う操作にサーバ側キーを要求する（fail-closed）。

    GOPIPE_API_KEY が未設定なら「誰でも自社キーで Claude を叩ける」状態なので、
    未設定そのものを 503 で拒否する。mock デモは無認証のまま通す。
    """
    expected = os.environ.get("GOPIPE_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{what} は停止中です（サーバ側 GOPIPE_API_KEY 未設定）。mock は利用できます。",
        )
    if not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=401,
            detail=f"{what} には x-gopipe-key ヘッダが必要です（provider=mock は不要）。",
        )


def _takeoff(provider: str, file: UploadFile | None, api_key: str | None = None):
    p = (provider or "mock").strip().lower()
    if p not in _FREE_PROVIDERS:
        _require_key(api_key, f"provider={p}")
    os.environ["GOPIPE_LLM_PROVIDER"] = p or "mock"
    from gopipe_takeoff import run_takeoff

    pdf = _save_upload(file)
    return run_takeoff(str(pdf), str(OUT))


@app.get("/", include_in_schema=False)
def root():
    # 素の URL はルート未定義で 404 になるため、/docs(Swagger UI) へ誘導する
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/docs")


@app.get("/share", include_in_schema=False)
def share():
    # 社員・クライアント共有用の公開ハブ（マンガ・使い方動画・デモ導線・共有文）。
    # 自己完結HTML。ログイン不要で誰でも閲覧できるよう素のHTMLResponseで返す。
    from fastapi.responses import HTMLResponse

    html = (Path(__file__).resolve().parent / "share.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/municipalities")
def municipalities():
    from gopipe_takeoff.application import _load_municipalities

    data = _load_municipalities()
    return {"municipalities": [m.get("name") for m in data.get("municipalities", [])]}


@app.post("/takeoff")
async def takeoff(
    provider: str = Form("mock"),
    persist: bool = Form(False),
    org_slug: str = Form("default"),
    project_slug: str = Form("takeoff"),
    title: str = Form(""),
    file: UploadFile | None = File(None),
    x_gopipe_key: str | None = Header(default=None),
):
    result = _takeoff(provider, file, x_gopipe_key)
    resp: dict = {"count": len(result.items), "items": _items_json(result.items)}
    if persist:
        # 書き込みは service_role（RLSバイパス）で走る。無認証で開けない。
        _require_key(x_gopipe_key, "persist=true")
        from gopipe_takeoff import store

        if store.is_enabled():
            try:
                resp["persisted"] = store.persist_takeoff(
                    org_slug=org_slug, org_name=org_slug,
                    project_slug=project_slug, title=title, items=result.items,
                )
            except Exception as e:  # 抽出は成功済み。保存失敗で全体は落とさない
                resp["persisted"] = {"error": str(e)}
        else:
            resp["persisted"] = {"error": "Supabase 未設定（SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY）"}
    return resp


@app.post("/estimate")
async def estimate(
    provider: str = Form("mock"),
    overhead: float = Form(0.10),
    file: UploadFile | None = File(None),
    x_gopipe_key: str | None = Header(default=None),
):
    from gopipe_takeoff.estimate import build_estimate
    from gopipe_takeoff.pricer import Pricer

    result = _takeoff(provider, file, x_gopipe_key)
    pricer = Pricer.from_yaml(_kpath("unit_prices.yaml"))
    est = build_estimate(result.items, pricer, overhead_rate=overhead)
    return {
        "subtotal": est.subtotal,
        "overhead": est.overhead,
        "tax": est.tax,
        "total": est.total,
        "lines": [
            {
                "category": ln.item.category, "name": ln.item.name, "spec": ln.item.spec,
                "quantity": ln.item.quantity, "unit": ln.item.unit,
                "unit_price": ln.unit_price, "amount": ln.amount,
                "material": ln.material, "labor": ln.labor,
            }
            for ln in est.lines
        ],
    }


@app.post("/application")
async def application(
    provider: str = Form("mock"),
    municipality: str = Form(""),
    contractor_name: str = Form(""),
    contractor_number: str = Form(""),
    chief_engineer: str = Form(""),
    owner: str = Form(""),
    address: str = Form(""),
    work_type: str = Form("改造"),
    file: UploadFile | None = File(None),
    x_gopipe_key: str | None = Header(default=None),
):
    from gopipe_takeoff.application import ProjectInfo, build_application_markdown

    result = _takeoff(provider, file, x_gopipe_key)
    proj = ProjectInfo(
        municipality=municipality, contractor_name=contractor_name,
        contractor_number=contractor_number, chief_engineer=chief_engineer,
        owner=owner, address=address, work_type=work_type,
    )
    return {"markdown": build_application_markdown(result.items, proj)}


@app.post("/maintenance")
async def maintenance(
    provider: str = Form("mock"),
    installed_year: int = Form(2008),
    current_year: int = Form(0),
    file: UploadFile | None = File(None),
    x_gopipe_key: str | None = Header(default=None),
):
    from gopipe_takeoff.maintenance import (
        build_ledger,
        build_maintenance_proposal,
        load_service_life,
        recommend_plan,
    )

    cy = current_year or datetime.date.today().year
    result = _takeoff(provider, file, x_gopipe_key)
    table, plans = load_service_life()
    ledger = build_ledger(result.items, installed_year, table)
    plan = recommend_plan(ledger, plans, current_year=cy)
    return {
        "plan": (
            {"name": plan.name, "monthly_fee": plan.monthly_fee,
             "interval_months": plan.interval_months, "scope": plan.scope}
            if plan else None
        ),
        "ledger": [
            {
                "name": r.item.name, "label": r.label, "spec": r.item.spec,
                "installed_year": r.installed_year, "service_life": r.service_life,
                "recommend_year": r.recommend_year, "remaining": r.remaining(cy),
            }
            for r in sorted(ledger, key=lambda r: r.remaining(cy))
        ],
        "markdown": build_maintenance_proposal(
            ledger, plan, plans, installed_year=installed_year, current_year=cy
        ),
    }


@app.post("/emergency")
async def emergency(symptom: str = Form(...)):
    from gopipe_takeoff.emergency import Catalog, build_quote_card, diagnose

    catalog = Catalog.from_yaml()
    cands = diagnose(symptom, catalog)
    return {
        "candidates": [
            {
                "name": c.job.name,
                "price_min_incl_tax": c.job.price_range_incl_tax()[0],
                "price_max_incl_tax": c.job.price_range_incl_tax()[1],
                "warranty_months": c.job.warranty_months,
                "score": c.score,
            }
            for c in cands
        ],
        "markdown": build_quote_card(symptom, cands),
    }


@app.post("/insulation")
async def insulation(rooms: list[dict] = Body(...), overhead: float = 0.10):
    """部屋寸法/面積（LiDAR・手測り）→ 断熱面積(壁/天井/床 m²)の拾い出し＋見積。

    rooms 例: [{"name":"LDK","width_m":5.4,"depth_m":4.2,"height_m":2.5,
                "exterior_wall_len_m":12,"openings_m2":8,
                "material":"断熱材(グラスウール)","thickness_mm":105}]
    LiDAR が面積を直接出す場合は floor_area_m2 / wall_area_m2 でも可。
    """
    from gopipe_takeoff.classifier import classify
    from gopipe_takeoff.dictionary import TakeoffDictionary
    from gopipe_takeoff.estimate import build_estimate
    from gopipe_takeoff.insulation_area import rooms_from_dicts, to_takeoff_items
    from gopipe_takeoff.pricer import Pricer

    items = classify(
        to_takeoff_items(rooms_from_dicts(rooms)),
        TakeoffDictionary.from_yaml(_kpath("dictionary.yaml")),
    )
    est = build_estimate(
        items, Pricer.from_yaml(_kpath("unit_prices.yaml")), overhead_rate=overhead
    )
    return {
        "count": len(items),
        "items": _items_json(items),
        "subtotal": est.subtotal,
        "total": est.total,
    }


@app.post("/site_measure")
async def site_measure(measures: list[dict] = Body(...), overhead: float = 0.10):
    """現地実測（LiDAR/巻尺）→ 空調・配管の拾い出し＋見積。

    measures 例: [{"kind":"角ダクト","name":"角ダクト","width_mm":500,"height_mm":400,"length_m":10},
                  {"kind":"配管","name":"冷温水配管","dia_mm":80,"length_m":12},
                  {"kind":"個数","name":"吹出口","count":8}]
    """
    from gopipe_takeoff.classifier import classify
    from gopipe_takeoff.dictionary import TakeoffDictionary
    from gopipe_takeoff.estimate import build_estimate
    from gopipe_takeoff.pricer import Pricer
    from gopipe_takeoff.site_measure import items_from_measures

    items = classify(
        items_from_measures(measures),
        TakeoffDictionary.from_yaml(_kpath("dictionary.yaml")),
    )
    est = build_estimate(
        items, Pricer.from_yaml(_kpath("unit_prices.yaml")), overhead_rate=overhead
    )
    return {
        "count": len(items),
        "items": _items_json(items),
        "subtotal": est.subtotal,
        "total": est.total,
    }


@app.post("/riser")
async def riser(risers: list[dict] = Body(...), overhead: float = 0.10):
    """系統図×階高 → 立管・隠蔽配管の延長/継手/弁を積算した拾い出し＋見積。

    平面図に長さが出ない立管を 階高×階数×本数 で延長(m)化し、継手・弁も階数比例で積算する。

    risers 例: [{"name":"給水立管 PS-1","floors":5,"floor_height_m":3.2,"count":2,
                 "spec":"VLP DN20","material":"給水管","branch_per_floor_m":3,
                 "fittings_per_floor":2,"valves_per_floor":1}]
    """
    from gopipe_takeoff.classifier import classify
    from gopipe_takeoff.dictionary import TakeoffDictionary
    from gopipe_takeoff.estimate import build_estimate
    from gopipe_takeoff.pricer import Pricer
    from gopipe_takeoff.riser_estimate import risers_from_dicts, to_takeoff_items

    items = classify(
        to_takeoff_items(risers_from_dicts(risers)),
        TakeoffDictionary.from_yaml(_kpath("dictionary.yaml")),
    )
    est = build_estimate(
        items, Pricer.from_yaml(_kpath("unit_prices.yaml")), overhead_rate=overhead
    )
    return {
        "count": len(items),
        "items": _items_json(items),
        "subtotal": est.subtotal,
        "total": est.total,
    }


@app.post("/legend_count")
async def legend_count(file: UploadFile | None = File(None), overhead: float = 0.10):
    """凡例（記号→名称）を解析し、テキスト層の記号出現数を機械カウント → 個数モノの拾い出し＋見積。

    ベクターPDF専用（テキスト層が必要）。スキャン図やテキスト層が無い場合は 0 件を返す。
    各記号は「総出現数 − 凡例定義1回」を図面配置数として個でカウントする。
    """
    from gopipe_takeoff.classifier import classify
    from gopipe_takeoff.dictionary import TakeoffDictionary
    from gopipe_takeoff.estimate import build_estimate
    from gopipe_takeoff.legend_count import count_from_pdf
    from gopipe_takeoff.pricer import Pricer

    pdf = _save_upload(file)
    if not Path(pdf).exists():
        return {"count": 0, "items": [], "subtotal": 0, "total": 0,
                "note": "ベクターPDF（テキスト層あり）をアップロードしてください"}
    items = classify(
        count_from_pdf(str(pdf)),
        TakeoffDictionary.from_yaml(_kpath("dictionary.yaml")),
    )
    est = build_estimate(
        items, Pricer.from_yaml(_kpath("unit_prices.yaml")), overhead_rate=overhead
    )
    return {
        "count": len(items),
        "items": _items_json(items),
        "subtotal": est.subtotal,
        "total": est.total,
    }
