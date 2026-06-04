"""GOPIPE Web UI（Streamlit）。

設備図PDF（または mock サンプル）から拾い出し → 見積(F-12) / 申請(F-16) /
予防保全(F-17) / 透明見積(F-15) をブラウザで実行・ダウンロードする。

起動:
    .venv/bin/streamlit run webui/app.py
    （mock なら PDF 不要でサンプルが動く。本番は LLMプロバイダ=claude＋設備図PDF）
"""
from __future__ import annotations

import datetime
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

# 既存パッケージ（src / shared）を import 可能にする
ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "src", ROOT / "shared"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

OUT_DIR = ROOT / "out"

st.set_page_config(page_title="GOPIPE", page_icon="🔧", layout="wide")


def _run_takeoff(pdf_path: Path, provider: str):
    os.environ["GOPIPE_LLM_PROVIDER"] = provider
    from gopipe_takeoff import run_takeoff

    return run_takeoff(str(pdf_path), str(OUT_DIR))


# ----------------------------- サイドバー -----------------------------
st.sidebar.title("🔧 GOPIPE")
st.sidebar.caption("配管・設備工事 AI ― 拾い出しから見積・申請・保全まで")
provider = st.sidebar.selectbox(
    "LLMプロバイダ",
    ["mock", "claude", "openai"],
    index=0,
    help="mock=APIキー不要のサンプル。claude=実図面の本番抽出（要 ANTHROPIC_API_KEY）",
)
uploaded = st.sidebar.file_uploader("設備図PDF", type=["pdf"])
run = st.sidebar.button("▶ 拾い出し実行", type="primary", use_container_width=True)
st.sidebar.markdown("---")
st.sidebar.caption("mock を選べば PDF 無しでサンプルが一気通貫で動きます。")

st.title("GOPIPE — 設備拾い出しから見積・申請・保全まで")

# ----------------------------- 断熱面積（実測/LiDAR・PDF不要） -----------------------------
with st.expander("🧱 断熱面積を計算（実測 / LiDAR・PDF不要）"):
    st.caption(
        "部屋の寸法 or 面積を入れて断熱面積(壁/天井/床 m²)→見積。"
        "LiDARアプリ(RoomPlan/Polycam等)の床面積・壁面積もそのまま使えます。"
        "外壁長を入れると内壁の二重計上を避け高精度に。"
    )
    _df0 = pd.DataFrame([
        {"室名": "LDK", "幅m": 5.4, "奥行m": 4.2, "天井高m": 2.5, "外壁長m": 12.0,
         "開口m2": 8.0, "床面積m2": None, "壁面積m2": None,
         "材種": "断熱材(グラスウール)", "厚みmm": 105, "部位": "壁;天井;床"},
    ])
    _edited = st.data_editor(_df0, num_rows="dynamic", use_container_width=True, key="ins_rooms")
    if st.button("断熱面積を算出", key="ins_run", type="primary"):
        from gopipe_takeoff.classifier import classify
        from gopipe_takeoff.dictionary import TakeoffDictionary
        from gopipe_takeoff.estimate import build_estimate
        from gopipe_takeoff.insulation_area import rooms_from_dicts, to_takeoff_items
        from gopipe_takeoff.pricer import Pricer

        _clean = _edited.astype(object).where(pd.notna(_edited), None)
        _recs = [
            {
                "name": r.get("室名"), "width_m": r.get("幅m"), "depth_m": r.get("奥行m"),
                "height_m": r.get("天井高m"), "exterior_wall_len_m": r.get("外壁長m"),
                "openings_m2": r.get("開口m2"), "floor_area_m2": r.get("床面積m2"),
                "wall_area_m2": r.get("壁面積m2"), "material": r.get("材種"),
                "thickness_mm": r.get("厚みmm"), "surfaces": r.get("部位"),
            }
            for _, r in _clean.iterrows()
        ]
        _ins = classify(
            to_takeoff_items(rooms_from_dicts(_recs)),
            TakeoffDictionary.from_yaml(ROOT / "prompts" / "dictionary.yaml"),
        )
        if _ins:
            st.dataframe(
                pd.DataFrame([
                    {"カテゴリ": it.category, "材種": it.name, "仕様": it.spec, "場所": it.location,
                     "数量": it.quantity, "単位": it.unit, "信頼度": round(it.confidence, 2)}
                    for it in _ins
                ]),
                use_container_width=True, hide_index=True,
            )
            _est = build_estimate(_ins, Pricer.from_yaml(ROOT / "prompts" / "unit_prices.yaml"))
            st.metric("断熱 見積（税込）", f"¥{_est.total:,}")
        else:
            st.warning("面積が算出できませんでした。寸法（幅・奥行・天井高）か、床面積/壁面積を入れてください。")

# ----------------------------- 現地実測（ダクト/配管/台数・LiDAR/巻尺・PDF不要） -----------------------------
with st.expander("📏 現地実測（ダクト/配管/台数・LiDAR/巻尺・PDF不要）"):
    st.caption(
        "SiteScape/巻尺で測った値を入れて空調拾い出し→見積。"
        "角ダクト=幅×高さ×延長→展開面積m²、丸ダクト=φ×延長、配管=口径×延長m、端末/機器=個数/台数。"
        "（種別: 角ダクト / 丸ダクト / 配管 / 個数 / 台数）"
    )
    _m0 = pd.DataFrame([
        {"種別": "角ダクト", "名称": "角ダクト", "幅mm": 500, "高さmm": 400, "口径mm": None, "延長m": 10.0, "個数": None, "場所": "1F 天井内"},
        {"種別": "配管", "名称": "冷温水配管", "幅mm": None, "高さmm": None, "口径mm": 80, "延長m": 12.0, "個数": None, "場所": "機械室"},
        {"種別": "個数", "名称": "吹出口", "幅mm": None, "高さmm": None, "口径mm": None, "延長m": None, "個数": 8, "場所": "1F 事務室"},
    ])
    _me = st.data_editor(_m0, num_rows="dynamic", use_container_width=True, key="sm_rows")
    if st.button("実測から算出", key="sm_run", type="primary"):
        from gopipe_takeoff.classifier import classify
        from gopipe_takeoff.dictionary import TakeoffDictionary
        from gopipe_takeoff.estimate import build_estimate
        from gopipe_takeoff.pricer import Pricer
        from gopipe_takeoff.site_measure import items_from_measures

        _c = _me.astype(object).where(pd.notna(_me), None)
        _ms = [
            {"kind": r.get("種別"), "name": r.get("名称"), "width_mm": r.get("幅mm"),
             "height_mm": r.get("高さmm"), "dia_mm": r.get("口径mm"), "length_m": r.get("延長m"),
             "count": r.get("個数"), "location": r.get("場所")}
            for _, r in _c.iterrows()
        ]
        _si = classify(
            items_from_measures(_ms),
            TakeoffDictionary.from_yaml(ROOT / "prompts" / "dictionary.yaml"),
        )
        if _si:
            st.dataframe(
                pd.DataFrame([
                    {"カテゴリ": it.category, "名称": it.name, "仕様": it.spec, "場所": it.location,
                     "数量": it.quantity, "単位": it.unit, "信頼度": round(it.confidence, 2)}
                    for it in _si
                ]),
                use_container_width=True, hide_index=True,
            )
            _e = build_estimate(_si, Pricer.from_yaml(ROOT / "prompts" / "unit_prices.yaml"))
            st.metric("空調(実測) 見積（税込）", f"¥{_e.total:,}")
        else:
            st.warning("算出できませんでした。種別（角ダクト/丸ダクト/配管/個数/台数）と寸法・個数を入れてください。")

# ----------------------------- 立管・延長計算（系統図×階高・PDF不要） -----------------------------
with st.expander("🧮 立管・延長計算（系統図×階高・PDF不要）"):
    st.caption(
        "平面図に長さが出ない立管を 階高×階数×本数 で延長(m)化。"
        "横引き・継手・弁は階数比例で積算。系統ごとに1行で入力してください。"
    )
    _r0 = pd.DataFrame([
        {"系統名": "給水立管 PS-1", "階数": 5, "階高m": 3.2, "本数": 2, "口径/仕様": "VLP DN20",
         "材種": "給水管", "横引きm/階": 3.0, "継手/階": 2, "弁/階": 1},
        {"系統名": "排水立管 PS-2", "階数": 5, "階高m": 3.2, "本数": 1, "口径/仕様": "VP100",
         "材種": "排水管", "横引きm/階": 2.0, "継手/階": 2, "弁/階": 0},
    ])
    _re = st.data_editor(_r0, num_rows="dynamic", use_container_width=True, key="riser_rows")
    if st.button("立管から算出", key="riser_run", type="primary"):
        from gopipe_takeoff.classifier import classify
        from gopipe_takeoff.dictionary import TakeoffDictionary
        from gopipe_takeoff.estimate import build_estimate
        from gopipe_takeoff.pricer import Pricer
        from gopipe_takeoff.riser_estimate import risers_from_dicts, to_takeoff_items

        _rc = _re.astype(object).where(pd.notna(_re), None)
        _rs = [
            {"name": r.get("系統名"), "floors": r.get("階数"), "floor_height_m": r.get("階高m"),
             "count": r.get("本数"), "spec": r.get("口径/仕様"), "material": r.get("材種"),
             "branch_per_floor_m": r.get("横引きm/階"), "fittings_per_floor": r.get("継手/階"),
             "valves_per_floor": r.get("弁/階")}
            for _, r in _rc.iterrows()
        ]
        _ri = classify(
            to_takeoff_items(risers_from_dicts(_rs)),
            TakeoffDictionary.from_yaml(ROOT / "prompts" / "dictionary.yaml"),
        )
        if _ri:
            st.dataframe(
                pd.DataFrame([
                    {"カテゴリ": it.category, "名称": it.name, "仕様": it.spec, "場所": it.location,
                     "数量": it.quantity, "単位": it.unit, "信頼度": round(it.confidence, 2)}
                    for it in _ri
                ]),
                use_container_width=True, hide_index=True,
            )
            _e = build_estimate(_ri, Pricer.from_yaml(ROOT / "prompts" / "unit_prices.yaml"))
            st.metric("立管(延長計算) 見積（税込）", f"¥{_e.total:,}")
        else:
            st.warning("算出できませんでした。各系統に『階数』と『階高m』を入れてください。")

# ----------------------------- 凡例ドリブン記号カウント（ベクターPDF・テキスト層） -----------------------------
with st.expander("🔣 凡例ドリブン記号カウント（ベクターPDF・テキスト層）"):
    st.caption(
        "凡例(記号→名称)を解析し、図面テキスト層の各記号の出現数を機械カウント→個数モノの拾い出し。"
        "CAD出力のベクターPDF向け（スキャン画像は0件になり得ます）。"
    )
    _lc_pdf = st.file_uploader("ベクターPDF（テキスト層あり）", type=["pdf"], key="lc_pdf")
    if st.button("凡例から記号カウント", key="lc_run", type="primary"):
        if _lc_pdf is None:
            st.warning("テキスト層のあるベクターPDFをアップロードしてください。")
        else:
            from gopipe_takeoff.classifier import classify
            from gopipe_takeoff.dictionary import TakeoffDictionary
            from gopipe_takeoff.estimate import build_estimate
            from gopipe_takeoff.legend_count import count_from_pdf
            from gopipe_takeoff.pricer import Pricer

            _tmp = Path(tempfile.gettempdir()) / _lc_pdf.name
            _tmp.write_bytes(_lc_pdf.getvalue())
            _lc = classify(
                count_from_pdf(str(_tmp)),
                TakeoffDictionary.from_yaml(ROOT / "prompts" / "dictionary.yaml"),
            )
            if _lc:
                st.dataframe(
                    pd.DataFrame([
                        {"カテゴリ": it.category, "名称": it.name, "記号": it.spec, "場所": it.location,
                         "数量": it.quantity, "単位": it.unit, "信頼度": round(it.confidence, 2)}
                        for it in _lc
                    ]),
                    use_container_width=True, hide_index=True,
                )
                _e = build_estimate(_lc, Pricer.from_yaml(ROOT / "prompts" / "unit_prices.yaml"))
                st.metric("記号カウント 見積（税込）", f"¥{_e.total:,}")
            else:
                st.info("凡例または記号が検出できませんでした。テキスト層のあるベクターPDFか確認してください。")

# ----------------------------- 実行 -----------------------------
if run:
    if uploaded is not None:
        tmp = Path(tempfile.gettempdir()) / uploaded.name
        tmp.write_bytes(uploaded.getvalue())
        pdf_path = tmp
    else:
        pdf_path = ROOT / "samples" / "dummy_設備図.pdf"
        if provider != "mock":
            st.warning("PDF が未選択です。mock 以外は設備図PDFをアップロードしてください。")
    with st.spinner("拾い出し中…"):
        try:
            result = _run_takeoff(pdf_path, provider)
            st.session_state["items"] = [it.model_dump() for it in result.items]
        except Exception as e:  # noqa: BLE001
            st.error(f"拾い出しでエラー: {e}")

# session_state から復元
items = None
if "items" in st.session_state:
    from gopipe_takeoff.models import TakeoffItem

    items = [TakeoffItem(**d) for d in st.session_state["items"]]

if not items:
    st.info("← サイドバーで LLMプロバイダを選び「拾い出し実行」を押してください"
            "（mock なら PDF 不要でサンプルが動きます）。")
    st.stop()

st.success(f"{len(items)} 件を抽出・系統別に分類しました。")

tab_take, tab_est, tab_app, tab_maint, tab_emg = st.tabs(
    ["📋 拾い出し", "💰 見積 (F-12)", "📄 申請 (F-16)", "🛡 予防保全 (F-17)", "🚿 透明見積 (F-15)"]
)

# ----------------------------- 拾い出し -----------------------------
with tab_take:
    df = pd.DataFrame(
        [
            {
                "カテゴリ": it.category, "名称": it.name, "仕様": it.spec,
                "場所": it.location, "数量": it.quantity, "単位": it.unit,
                "信頼度": round(it.confidence, 2),
            }
            for it in items
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

# ----------------------------- 見積 (F-12) -----------------------------
with tab_est:
    from gopipe_takeoff.estimate import (
        build_estimate,
        write_estimate_excel,
        write_purchase_order_excel,
    )
    from gopipe_takeoff.pricer import Pricer

    overhead = st.slider("諸経費率", 0.0, 0.30, 0.10, 0.01)
    pricer = Pricer.from_yaml(ROOT / "prompts" / "unit_prices.yaml")
    est = build_estimate(items, pricer, overhead_rate=overhead)

    c1, c2, c3 = st.columns(3)
    c1.metric("小計", f"¥{est.subtotal:,}")
    c2.metric("諸経費＋消費税", f"¥{est.overhead + est.tax:,}")
    c3.metric("合計（税込）", f"¥{est.total:,}")

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "カテゴリ": ln.item.category, "名称": ln.item.name, "仕様": ln.item.spec,
                    "数量": ln.item.quantity, "単位": ln.item.unit,
                    "単価": ln.unit_price, "金額": ln.amount,
                    "材料費": ln.material, "労務費": ln.labor,
                }
                for ln in est.lines
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    ep = write_estimate_excel(est, OUT_DIR / "見積書.xlsx")
    pp = write_purchase_order_excel(est, OUT_DIR / "材料発注書.xlsx")
    d1, d2 = st.columns(2)
    d1.download_button("⬇ 見積書.xlsx", ep.read_bytes(), "見積書.xlsx", use_container_width=True)
    d2.download_button("⬇ 材料発注書.xlsx", pp.read_bytes(), "材料発注書.xlsx", use_container_width=True)

# ----------------------------- 申請 (F-16) -----------------------------
with tab_app:
    from gopipe_takeoff.application import (
        ProjectInfo,
        _load_municipalities,
        build_application_markdown,
    )

    data = _load_municipalities()
    names = [m.get("name", "") for m in data.get("municipalities", [])]
    muni = st.selectbox("提出先自治体", names + ["（その他／汎用）"])
    c1, c2 = st.columns(2)
    contractor = c1.text_input("指定給水装置工事事業者名", "")
    number = c2.text_input("指定番号", "")
    chief = c1.text_input("主任技術者", "")
    owner = c2.text_input("施主・使用者", "")
    addr = st.text_input("工事場所（住所）", "")
    work_type = st.selectbox("工事種別", ["新設", "改造", "撤去", "修繕"], index=1)

    proj = ProjectInfo(
        municipality="" if muni == "（その他／汎用）" else muni,
        contractor_name=contractor, contractor_number=number,
        chief_engineer=chief, owner=owner, address=addr, work_type=work_type,
    )
    md = build_application_markdown(items, proj)
    st.markdown(md)
    st.download_button(
        "⬇ 給水装置工事申込書_ドラフト.md", md.encode("utf-8"),
        "給水装置工事申込書_ドラフト.md", use_container_width=True,
    )

# ----------------------------- 予防保全 (F-17) -----------------------------
with tab_maint:
    from gopipe_takeoff.maintenance import (
        build_ledger,
        build_maintenance_proposal,
        load_service_life,
        recommend_plan,
    )

    c1, c2 = st.columns(2)
    installed = c1.number_input("布設年（西暦）", 1970, 2030, 2008)
    current = c2.number_input("評価年（西暦）", 2000, 2100, datetime.date.today().year)
    table, plans = load_service_life()
    ledger = build_ledger(items, int(installed), table)
    plan = recommend_plan(ledger, plans, current_year=int(current))
    n_due = sum(1 for r in ledger if r.remaining(int(current)) <= 0)

    m1, m2, m3 = st.columns(3)
    m1.metric("台帳件数", len(ledger))
    m2.metric("更新時期超過", n_due)
    m3.metric("推奨プラン", plan.name if plan else "—")
    if plan:
        st.info(f"**{plan.name}** ／ 月額 ¥{plan.monthly_fee:,}（{plan.interval_months}ヶ月ごと）— {plan.scope}")

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "名称": r.item.name, "管種": r.label, "仕様": r.item.spec,
                    "布設年": r.installed_year, "耐用年数": r.service_life,
                    "更新推奨年": r.recommend_year, "残存年": r.remaining(int(current)),
                }
                for r in sorted(ledger, key=lambda r: r.remaining(int(current)))
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    md = build_maintenance_proposal(
        ledger, plan, plans, installed_year=int(installed), current_year=int(current)
    )
    st.download_button(
        "⬇ 予防保全プラン提案.md", md.encode("utf-8"),
        "予防保全プラン提案.md", use_container_width=True,
    )

# ----------------------------- 透明見積 (F-15) -----------------------------
with tab_emg:
    from gopipe_takeoff.emergency import Catalog, build_quote_card, diagnose

    st.caption("症状から標準作業と明朗料金レンジを提示します（拾い出しとは独立して使えます）。")
    symptom = st.text_input("症状", "トイレが流れない 水位が上がる")
    catalog = Catalog.from_yaml()
    cands = diagnose(symptom, catalog)
    for c in cands:
        lo, hi = c.job.price_range_incl_tax()
        warranty = f"保証{c.job.warranty_months}ヶ月" if c.job.warranty_months else "保証—"
        st.write(f"**{c.job.name}** … ¥{lo:,} 〜 ¥{hi:,}（{warranty}）")
    card = build_quote_card(symptom, cands)
    with st.expander("透明見積カード（Markdown）を表示"):
        st.markdown(card)
    st.download_button(
        "⬇ 透明見積カード.md", card.encode("utf-8"),
        "透明見積カード.md", use_container_width=True,
    )
