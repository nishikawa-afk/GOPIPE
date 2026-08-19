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

from gopipe_takeoff.locale import available_locales as _locales  # noqa: E402
from gopipe_takeoff.locale import money_for as _money_for  # noqa: E402
from gopipe_takeoff.locale import resolve as _kpath  # noqa: E402

# Streamlit Community Cloud: Secrets を環境変数へ橋渡し（claude/openai プロバイダ用）。
# 未設定でも mock と各計算機能（断熱/実測/立管/凡例）は動作する。
try:
    for _k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

OUT_DIR = ROOT / "out"

st.set_page_config(page_title="GOPIPE — 未来へPIPEを架ける", page_icon="🔧", layout="wide")

st.markdown(
    """<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800;900&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap');
:root{--gp-bg:#0A1020;--gp-panel:#101a36;--gp-cyan:#22D3EE;--gp-blue:#3B82F6;--gp-orange:#F59E0B;--gp-text:#E6F0FF;--gp-dim:#8aa0c8;}
.stApp{
  background:
    radial-gradient(1200px 600px at 12% -10%, rgba(34,211,238,.16), transparent 60%),
    radial-gradient(1000px 520px at 95% 0%, rgba(245,147,58,.12), transparent 55%),
    radial-gradient(900px 700px at 50% 120%, rgba(59,130,246,.18), transparent 60%),
    linear-gradient(180deg,#0A1020 0%,#0b1228 50%,#0a0f1f 100%);
  background-attachment:fixed; color:var(--gp-text);
  font-family:'Zen Kaku Gothic New','Noto Sans JP',sans-serif;
}
.stApp:before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.55;
  background-image:linear-gradient(rgba(34,211,238,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,.06) 1px,transparent 1px);
  background-size:46px 46px;
  -webkit-mask-image:radial-gradient(1200px 640px at 50% 0%,#000 28%,transparent 80%);
  mask-image:radial-gradient(1200px 640px at 50% 0%,#000 28%,transparent 80%);
  animation:gpGrid 26s linear infinite;}
@keyframes gpGrid{from{background-position:0 0,0 0}to{background-position:46px 46px,46px 46px}}
[data-testid="stHeader"]{background:transparent;}
.block-container{position:relative;z-index:1;padding-top:2.2rem;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,rgba(16,26,54,.94),rgba(10,16,32,.94));border-right:1px solid rgba(34,211,238,.22);backdrop-filter:blur(8px);}
[data-testid="stSidebar"] *{color:var(--gp-text);}
[data-testid="stMarkdownContainer"] h2{background:linear-gradient(90deg,#fff,#9be9ff 60%,var(--gp-cyan));-webkit-background-clip:text;background-clip:text;color:transparent;font-weight:900;}
[data-testid="stMarkdownContainer"] h3{color:#bfe6ff;}
.stButton>button{border-radius:12px;border:1px solid rgba(34,211,238,.45);background:linear-gradient(135deg,rgba(34,211,238,.16),rgba(59,130,246,.16));color:var(--gp-text);font-weight:700;transition:.2s;}
.stButton>button:hover{border-color:var(--gp-cyan);box-shadow:0 0 22px rgba(34,211,238,.45),inset 0 0 12px rgba(34,211,238,.15);transform:translateY(-1px);}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,var(--gp-orange),#ff7a1a);border:none;color:#1a1206;box-shadow:0 0 24px rgba(245,147,58,.5);}
.stButton>button[kind="primary"]:hover{box-shadow:0 0 36px rgba(245,147,58,.85);}
[data-testid="stExpander"]{border:1px solid rgba(34,211,238,.22);border-radius:14px;background:linear-gradient(180deg,rgba(17,26,51,.7),rgba(12,18,38,.6));backdrop-filter:blur(6px);overflow:hidden;margin-bottom:.55rem;box-shadow:0 8px 30px rgba(0,0,0,.35);transition:.2s;}
[data-testid="stExpander"]:hover{border-color:rgba(34,211,238,.55);box-shadow:0 0 26px rgba(34,211,238,.18);}
[data-testid="stExpander"] summary{font-weight:700;color:var(--gp-text);}
[data-testid="stExpander"] summary:hover{color:var(--gp-cyan);}
[data-testid="stFileUploaderDropzone"]{background:rgba(17,26,51,.6);border:1px dashed rgba(34,211,238,.4);}
[data-baseweb="select"]>div{background:rgba(17,26,51,.85);border-color:rgba(34,211,238,.3);}
[data-testid="stMetricValue"]{color:var(--gp-cyan);text-shadow:0 0 18px rgba(34,211,238,.45);font-weight:800;}
[data-testid="stDataFrame"]{border:1px solid rgba(34,211,238,.18);border-radius:12px;}
[data-testid="stAlert"]{background:rgba(34,211,238,.08);border:1px solid rgba(34,211,238,.3);border-radius:12px;}
[data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid rgba(34,211,238,.15);}
[aria-selected="true"][data-baseweb="tab"]{color:var(--gp-cyan);}
[data-baseweb="tab-highlight"]{background:var(--gp-cyan)!important;box-shadow:0 0 12px var(--gp-cyan);}
/* ---- HERO ---- */
.gp-hero{position:relative;margin:.1rem 0 1.3rem;padding:26px 30px 14px;border-radius:20px;overflow:hidden;
  background:radial-gradient(800px 320px at 82% -40%,rgba(245,147,58,.18),transparent 60%),radial-gradient(720px 340px at 8% 0%,rgba(34,211,238,.20),transparent 60%),linear-gradient(135deg,rgba(13,21,48,.96),rgba(9,14,31,.93));
  border:1px solid rgba(34,211,238,.28);box-shadow:0 22px 60px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.05);}
.gp-kicker{font-family:'Orbitron',sans-serif;font-size:.7rem;letter-spacing:.4em;color:var(--gp-cyan);text-transform:uppercase;opacity:.85;margin-bottom:6px;}
.gp-title{font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(2.6rem,6.4vw,4.4rem);line-height:1;margin:0;letter-spacing:.04em;
  background:linear-gradient(92deg,#eaffff 0%,#6fe9ff 36%,#3aa0ff 62%,#ffb259 100%);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 0 26px rgba(34,211,238,.35));}
.gp-sub{font-size:clamp(1.1rem,2.4vw,1.55rem);font-weight:900;margin:.55rem 0 .1rem;color:#fff;text-shadow:0 0 22px rgba(34,211,238,.35);}
.gp-desc{color:var(--gp-dim);margin:.1rem 0 .2rem;font-size:.97rem;}
.gp-pipe{width:100%;height:auto;display:block;margin-top:10px;}
.gp-flow{stroke-dasharray:14 16;animation:gpFlow 1.5s linear infinite;}
@keyframes gpFlow{to{stroke-dashoffset:-30;}}
.gp-node{filter:drop-shadow(0 0 6px rgba(34,211,238,.7));}
.gp-future{animation:gpPulse 2.2s ease-in-out infinite;transform-origin:center;}
@keyframes gpPulse{0%,100%{filter:drop-shadow(0 0 6px rgba(245,147,58,.55));}50%{filter:drop-shadow(0 0 22px rgba(245,147,58,1));}}
.gp-label{font-family:'Zen Kaku Gothic New',sans-serif;font-size:13px;fill:#cfe3ff;}
.gp-label.f{fill:#ffd9a8;font-weight:700;}
/* ---- 起動スプラッシュ（コールドスタートの暗転対策・CSSのみで自動フェード） ---- */
.gp-splash{position:fixed;inset:0;z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;
  background:radial-gradient(900px 600px at 50% 30%,rgba(34,211,238,.12),transparent 60%),linear-gradient(180deg,#0A1020,#0a0f1f);
  animation:gpSplash 1.4s ease forwards;pointer-events:none;}
@keyframes gpSplash{0%,50%{opacity:1;}100%{opacity:0;visibility:hidden;}}
.gp-splash .l{font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(2.4rem,7vw,3.6rem);letter-spacing:.12em;
  background:linear-gradient(92deg,#eaffff,#6fe9ff 40%,#ffb259);-webkit-background-clip:text;background-clip:text;color:transparent;
  animation:gpSplashPulse 1s ease-in-out infinite;}
.gp-splash .s{font-family:'Zen Kaku Gothic New',sans-serif;color:#8aa0c8;font-size:.85rem;letter-spacing:.25em;}
@keyframes gpSplashPulse{0%,100%{filter:drop-shadow(0 0 8px rgba(34,211,238,.4));}50%{filter:drop-shadow(0 0 26px rgba(34,211,238,.9));}}
/* ---- モバイル最適化（現場・経営者がスマホで見る前提） ---- */
@media (max-width:640px){
  .block-container{padding-left:.55rem;padding-right:.55rem;padding-top:1.2rem;}
  .gp-hero{padding:18px 16px 8px;}
  .gp-title{font-size:2.4rem;}
  [data-testid="column"]{width:100%!important;flex:1 1 100%!important;min-width:100%!important;}
  [data-testid="stMetric"]{text-align:center;border:1px solid rgba(34,211,238,.18);border-radius:12px;padding:8px 4px;margin-bottom:6px;background:rgba(17,26,51,.5);}
  [data-testid="stDownloadButton"] button,.stButton>button{width:100%!important;}
}
</style>""",
    unsafe_allow_html=True,
)

# 起動スプラッシュ（早期に描画 → CSSアニメで自動フェードアウト）
st.markdown(
    '<div class="gp-splash"><div class="l">GOPIPE</div>'
    '<div class="s">LOADING · PIPING AI</div></div>',
    unsafe_allow_html=True,
)


def _run_takeoff(pdf_path: Path, provider: str, *, grid: int = 1, two_pass: bool = False):
    os.environ["GOPIPE_LLM_PROVIDER"] = provider
    from gopipe_takeoff import run_takeoff

    return run_takeoff(str(pdf_path), str(OUT_DIR), grid=grid, two_pass=two_pass)


def _conf_badge(c: float) -> str:
    """信頼度を色付きバッジ文字列に（赤<0.7 / 黄<0.85 / 緑）。"""
    dot = "🔴" if c < 0.7 else ("🟡" if c < 0.85 else "🟢")
    return f"{dot} {c:.2f}"


def _build_deliverables_zip(_items) -> bytes:
    """拾い出し・見積サマリ・申請書を1つのZIPにまとめて bytes を返す。"""
    import io
    import zipfile

    from gopipe_takeoff.application import ProjectInfo, build_application_markdown
    from gopipe_takeoff.estimate import build_estimate as _zbe
    from gopipe_takeoff.excel_writer import write_excel
    from gopipe_takeoff.pricer import Pricer as _zpr

    _tmpx = Path(tempfile.gettempdir()) / "gopipe_toridashi.xlsx"
    write_excel(_items, _tmpx)
    _zest = _zbe(_items, _zpr.from_yaml(_kpath("unit_prices.yaml")))
    _zmd = build_application_markdown(_items, ProjectInfo(municipality="東京都水道局"))
    _zsum = f"GOPIPE 見積サマリ\n小計(税抜): ¥{_zest.subtotal:,}\n合計(税込): ¥{_zest.total:,}\n"
    _zbuf = io.BytesIO()
    with zipfile.ZipFile(_zbuf, "w", zipfile.ZIP_DEFLATED) as _z:
        _z.write(_tmpx, "拾い出し表.xlsx")
        _z.writestr("見積サマリ.txt", _zsum)
        _z.writestr("給水装置工事申込書.md", _zmd)
    return _zbuf.getvalue()


# ----------------------------- サイドバー -----------------------------
st.sidebar.title("🔧 GOPIPE")
st.sidebar.caption("配管・設備工事 AI ― 拾い出しから見積・申請・保全まで")
provider = st.sidebar.selectbox(
    "LLMプロバイダ",
    ["mock", "claude", "openai"],
    index=0,
    help="mock=APIキー不要のサンプル。claude=実図面の本番抽出（要 ANTHROPIC_API_KEY）",
)
_loc_opts = _locales()
_loc = st.sidebar.selectbox(
    "言語 / Locale", _loc_opts,
    index=(_loc_opts.index("ja") if "ja" in _loc_opts else 0),
    help="知識(辞書/単価/抽出プロンプト)を国コードで切替。en は海外展開の基盤(prompts/en)。",
)
os.environ["GOPIPE_LOCALE"] = _loc

# ----- i18n（主要文言。残りは順次。海外展開の土台 / VISION.md）-----
I18N = {
    "ja": {
        "hero_sub": "未来へ、PIPEを架ける。",
        "hero_desc": "拾い出し → 見積 → 申請 → 保全。設備積算を、AIで“いま”から“未来”へつなぐ。",
        "run": "▶ 拾い出し実行",
        "tab_take": "📋 拾い出し", "tab_view": "📐 図面プレビュー", "tab_bench": "📊 精度",
        "tab_est": "💰 見積", "tab_app": "📄 申請", "tab_maint": "🛡 予防保全", "tab_emg": "🚿 透明見積",
    },
    "en": {
        "hero_sub": "Bridging takeoff to the future.",
        "hero_desc": "Takeoff → Estimate → Filing → Maintenance. Construction takeoff, from now to the future — with AI.",
        "run": "▶ Run Takeoff",
        "tab_take": "📋 Takeoff", "tab_view": "📐 Drawing", "tab_bench": "📊 Accuracy",
        "tab_est": "💰 Estimate", "tab_app": "📄 Filing", "tab_maint": "🛡 Maintenance", "tab_emg": "🚿 Transparent",
    },
}


def _t(key: str) -> str:
    return I18N.get(_loc, I18N["ja"]).get(key, I18N["ja"].get(key, key))
uploaded = st.sidebar.file_uploader("設備図PDF", type=["pdf"])
with st.sidebar.expander("⚙ 高精度モード（スキャン図向け）"):
    _grid = st.select_slider(
        "タイル分割（細かいほど高精度・低速）", options=[1, 2, 3], value=1,
        help="図面を grid×grid に分割してAIに渡し、小さな数量も読みやすくします（API回数 grid² 倍）。",
    )
    _two_pass = st.checkbox(
        "多パス（漏れ確認）", value=False,
        help="抽出後にもう一度『漏れがないか』をAIに確認させます（API +1回/ページ）。",
    )
run = st.sidebar.button(_t("run"), type="primary", use_container_width=True)
st.sidebar.markdown("---")
try:
    from gopipe_takeoff.learned import load_aliases as _la0
    _lc0 = len(_la0())
    if _lc0:
        st.sidebar.caption(f"🧠 学習の堀：別名 {_lc0} 件を分類に反映中")
except Exception:  # noqa: BLE001
    pass
st.sidebar.caption("mock を選べば PDF 無しでサンプルが一気通貫で動きます。")

st.markdown(
    f"""
<div class="gp-hero">
  <div class="gp-kicker">PIPING · HVAC · INSULATION — AI TAKEOFF</div>
  <div class="gp-title">GOPIPE</div>
  <div class="gp-sub">{_t('hero_sub')}</div>
  <div class="gp-desc">{_t('hero_desc')}</div>
  <svg class="gp-pipe" viewBox="0 0 1200 150" preserveAspectRatio="xMidYMid meet" role="img" aria-label="未来へ架かるパイプ">
    <defs>
      <linearGradient id="gpPg" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#22D3EE"/><stop offset="0.6" stop-color="#3B82F6"/><stop offset="1" stop-color="#F59E0B"/>
      </linearGradient>
      <filter id="gpGlow" x="-20%" y="-50%" width="140%" height="200%">
        <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>
    <path d="M30,112 C 300,112 360,46 600,46 S 900,40 1170,30" fill="none" stroke="rgba(34,211,238,.18)" stroke-width="14" stroke-linecap="round"/>
    <path d="M30,112 C 300,112 360,46 600,46 S 900,40 1170,30" fill="none" stroke="url(#gpPg)" stroke-width="4" stroke-linecap="round" filter="url(#gpGlow)"/>
    <path class="gp-flow" d="M30,112 C 300,112 360,46 600,46 S 900,40 1170,30" fill="none" stroke="#eafdff" stroke-width="2.4" stroke-linecap="round"/>
    <g class="gp-node"><circle cx="30" cy="112" r="7" fill="#22D3EE"/></g>
    <g class="gp-node"><circle cx="330" cy="82" r="6.5" fill="#39c6f0"/></g>
    <g class="gp-node"><circle cx="600" cy="46" r="6.5" fill="#4aa6f2"/></g>
    <g class="gp-node"><circle cx="900" cy="41" r="6.5" fill="#7f9ff4"/></g>
    <g class="gp-future"><circle cx="1170" cy="30" r="9" fill="#F59E0B"/></g>
    <text class="gp-label" x="22" y="135" text-anchor="start">設備図 / 実測</text>
    <text class="gp-label" x="330" y="106" text-anchor="middle">AI 拾い出し</text>
    <text class="gp-label" x="600" y="70" text-anchor="middle">見積 / 発注</text>
    <text class="gp-label" x="900" y="65" text-anchor="middle">申請 / 保全</text>
    <text class="gp-label f" x="1178" y="20" text-anchor="end">未来 →</text>
  </svg>
</div>
""",
    unsafe_allow_html=True,
)

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
            TakeoffDictionary.from_yaml(_kpath("dictionary.yaml")),
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
            _est = build_estimate(_ins, Pricer.from_yaml(_kpath("unit_prices.yaml")))
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
            TakeoffDictionary.from_yaml(_kpath("dictionary.yaml")),
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
            _e = build_estimate(_si, Pricer.from_yaml(_kpath("unit_prices.yaml")))
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
            TakeoffDictionary.from_yaml(_kpath("dictionary.yaml")),
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
            _e = build_estimate(_ri, Pricer.from_yaml(_kpath("unit_prices.yaml")))
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
                TakeoffDictionary.from_yaml(_kpath("dictionary.yaml")),
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
                _e = build_estimate(_lc, Pricer.from_yaml(_kpath("unit_prices.yaml")))
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
    if uploaded is not None:
        try:
            from gopipe_takeoff.equipment_table import has_text_layer
            if has_text_layer(str(pdf_path)):
                st.success("✅ ベクターPDF（テキスト層あり）を検出 — 機器表テキスト抽出が効き、高精度が期待できます。")
            else:
                st.warning("⚠ スキャン画像PDF（テキスト層なし）の可能性 — 数量が読めない場合があります。可能ならCAD出力のベクターPDFを推奨します。")
        except Exception:  # noqa: BLE001
            pass
    with st.spinner("拾い出し中…"):
        try:
            result = _run_takeoff(pdf_path, provider, grid=_grid, two_pass=_two_pass)
            _items = result.items
            try:  # 学習の堀: これまでの修正(学習別名)を反映して再分類
                from gopipe_takeoff.classifier import classify as _cls
                from gopipe_takeoff.dictionary import TakeoffDictionary as _TD
                from gopipe_takeoff.learned import load_aliases as _la
                _d = _TD.from_yaml(_kpath("dictionary.yaml"))
                _d.add_learned(_la())
                _items = _cls(result.items, _d)
            except Exception:  # noqa: BLE001
                pass
            st.session_state["items"] = [it.model_dump() for it in _items]
            try:  # 図面プレビュー用にAIマーカーPDFを退避
                _mp = result.marker_pdf_path
                st.session_state["marker_pdf"] = (
                    Path(_mp).read_bytes() if _mp and Path(_mp).exists() else None
                )
            except Exception:  # noqa: BLE001
                st.session_state["marker_pdf"] = None
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

with st.expander("📦 成果物を一括ダウンロード（ZIP：拾い出し・見積・申請）"):
    if st.button("ZIPを生成", key="zip_gen"):
        st.download_button(
            "⬇ GOPIPE成果物.zip をダウンロード", _build_deliverables_zip(items),
            file_name="GOPIPE成果物.zip", mime="application/zip", key="zip_dl",
        )
        st.success("ZIPを生成しました。下のボタンで保存できます。")

tab_take, tab_view, tab_bench, tab_est, tab_app, tab_maint, tab_emg = st.tabs(
    [_t("tab_take"), _t("tab_view"), _t("tab_bench"), _t("tab_est"),
     _t("tab_app"), _t("tab_maint"), _t("tab_emg")]
)

# ----------------------------- 拾い出し -----------------------------
with tab_take:
    from gopipe_takeoff import validate_items as _vchk
    from gopipe_takeoff.estimate import build_estimate as _be
    from gopipe_takeoff.models import TakeoffItem as _TI
    from gopipe_takeoff.pricer import Pricer as _pr

    def _is_warn(it) -> bool:
        return it.confidence < 0.7 or bool(_vchk.check_item(it))

    _low = [it for it in items if it.confidence < 0.7]
    _flags = _vchk.check(items)
    _warn_items = [it for it in items if _is_warn(it)]
    _c1, _c2, _c3 = st.columns(3)
    _c1.metric("抽出 件数", len(items))
    _c2.metric("要確認 (信頼度<0.7)", len(_low))
    _c3.metric("整合チェック フラグ", len(_flags))
    st.caption(
        "AIの下書きです。数量・名称・仕様はその場で修正できます。"
        "🔴＝要確認（信頼度<0.7 か 整合チェック該当）で、要確認の行を表の上にまとめています。"
        "修正→『🔄 反映して再見積』→ 確定したら『✅ 学習に記録』で次回の精度に還元されます。"
    )
    # 要確認(🔴)を上に集約 → その中で信頼度の低い順。整合チェックの理由も前寄せで表示。
    _sorted_items = sorted(items, key=lambda x: (0 if _is_warn(x) else 1, x.confidence))
    _rev_src = pd.DataFrame(
        [
            {"⚠": "🔴" if _is_warn(it) else "",
             "確度": _conf_badge(it.confidence),
             "チェック": " / ".join(_vchk.check_item(it)),
             "名称": it.name, "数量": float(it.quantity), "単位": it.unit or "",
             "カテゴリ": it.category or "", "仕様": it.spec or "", "場所": it.location or ""}
            for it in _sorted_items
        ]
    )
    _edited = st.data_editor(
        _rev_src, use_container_width=True, hide_index=True, num_rows="dynamic",
        key="review_tbl", disabled=["⚠", "確度", "チェック"],
        column_config={
            "⚠": st.column_config.TextColumn("⚠", width="small", help="🔴＝要確認"),
            "確度": st.column_config.TextColumn("確度", width="small",
                                              help="🔴<0.7 / 🟡<0.85 / 🟢 それ以上"),
            "チェック": st.column_config.TextColumn("チェック", width="medium",
                                                help="整合チェックの指摘（数量0・単位×カテゴリ不一致・外れ値・重複）"),
            "名称": st.column_config.TextColumn("名称", width="large"),
            "数量": st.column_config.NumberColumn("数量", width="small"),
        },
    )
    _b1, _b2 = st.columns(2)
    if _b1.button("🔄 反映して再見積", key="review_reest", use_container_width=True):
        _e = _edited.astype(object).where(pd.notna(_edited), None)
        _rev = [
            _TI(page=1, name=str(r.get("名称") or "").strip(), spec=(r.get("仕様") or None),
                quantity=float(r.get("数量") or 0), unit=str(r.get("単位") or ""),
                location=(r.get("場所") or None), category=(r.get("カテゴリ") or None),
                confidence=1.0)  # 人が確認・修正した行は確定扱い
            for _, r in _e.iterrows() if str(r.get("名称") or "").strip()
        ]
        st.session_state["items"] = [it.model_dump() for it in _rev]
        _est = _be(_rev, _pr.from_yaml(_kpath("unit_prices.yaml")))
        st.metric("修正後 見積（税込）", f"¥{_est.total:,}")
        st.success(f"{len(_rev)} 件で再計算しました。各タブにも反映されます。")
    if _b2.button("✅ 学習に記録（確定）", key="review_learn", use_container_width=True):
        from gopipe_takeoff.feedback import record_correction
        from gopipe_takeoff.learned import record_alias
        _e = _edited.astype(object).where(pd.notna(_edited), None)
        _ts = datetime.date.today().isoformat()
        _n = _learned = 0
        for _i in range(min(len(_rev_src), len(_e))):
            _o = _rev_src.iloc[_i]
            _r = _e.iloc[_i]
            _on = str(_o["名称"])
            _nn = str(_r.get("名称") or "").strip()
            if not _nn:
                continue
            _bef = {"name": _on, "spec": (_o["仕様"] or None), "quantity": float(_o["数量"]),
                    "unit": (_o["単位"] or None), "category": (_o["カテゴリ"] or None)}
            _aft = {"name": _nn, "spec": (_r.get("仕様") or None), "quantity": float(_r.get("数量") or 0),
                    "unit": (_r.get("単位") or None), "category": (_r.get("カテゴリ") or None)}
            try:
                record_correction(project="webui", before=_bef, after=_aft, ts=_ts)
                _n += 1
            except Exception:  # noqa: BLE001
                pass
            if (_on != _nn) or (str(_o["カテゴリ"] or "") != str(_r.get("カテゴリ") or "")) \
                    or (str(_o["単位"] or "") != str(_r.get("単位") or "")):
                try:
                    if record_alias(_on, _nn, category=(_r.get("カテゴリ") or None), unit=(_r.get("単位") or None)):
                        _learned += 1
                except Exception:  # noqa: BLE001
                    pass
        if _learned:
            st.success(
                f"{_n} 件を確定・うち {_learned} 件を『学習の堀』に反映しました"
                "（次回、同じ表記を自動で正しく分類します）。"
            )
            st.balloons()
        else:
            st.success(
                f"{_n} 件を確定しました（修正がなかったため新規の学習はなし＝分類は全件そのまま確定）。"
            )
        # 確定した内容の“出口”をこの場でも提供（ボタン直後に成果物ZIP）
        st.download_button(
            "📦 この内容で成果物ZIPをダウンロード", _build_deliverables_zip(items),
            file_name="GOPIPE成果物.zip", mime="application/zip",
            key="zip_after_confirm", use_container_width=True,
        )

# ----------------------------- 図面プレビュー（AIマーカー） -----------------------------
with tab_view:
    _mp = st.session_state.get("marker_pdf")
    if not _mp:
        st.info(
            "実図面PDFをアップロードして（高精度モードのタイル分割なし＝grid=1で）拾い出すと、"
            "AIが検出した部材をカテゴリ色で重ねた『AIマーカー図』が表示されます。"
            "mock・タイル分割時は座標が無いため表示されません。"
        )
    else:
        import fitz as _fitz

        st.caption("AIが検出した部材をカテゴリ色で図面に重ねた『AIマーカー図』です（給水=青/弁類=赤/機器=紫…）。")
        _doc = _fitz.open(stream=_mp, filetype="pdf")
        for _pno in range(min(_doc.page_count, 5)):
            _png = _doc[_pno].get_pixmap(dpi=110).tobytes("png")
            st.image(_png, caption=f"ページ {_pno + 1}")
        _doc.close()
        st.download_button(
            "⬇ AIマーカー図(PDF)をダウンロード", _mp,
            file_name="AIマーカー図.pdf", mime="application/pdf", key="marker_dl",
        )

# ----------------------------- 精度ダッシュボード -----------------------------
with tab_bench:
    st.caption(
        "人手の正解CSV（列: name,spec,location,quantity,unit,category）をアップロードすると、"
        "現在の拾い出しとの一致率を測定します。雛形は samples/truth_template.csv。"
    )
    _tf = st.file_uploader("正解CSV をアップロード", type=["csv"], key="bench_truth")
    if _tf is not None:
        import csv as _csv
        import io as _io

        from gopipe_takeoff.benchmark import benchmark as _bench
        try:
            _truth = list(_csv.DictReader(_io.StringIO(_tf.getvalue().decode("utf-8-sig"))))
            _ai = [
                {"category": it.category, "name": it.name, "spec": it.spec,
                 "location": it.location, "quantity": it.quantity, "unit": it.unit}
                for it in items
            ]
            _br = _bench(_ai, _truth)
            _bc1, _bc2 = st.columns(2)
            _bc1.metric("適合率 precision", f"{_br.precision * 100:.0f}%")
            _bc2.metric("再現率 recall", f"{_br.recall * 100:.0f}%")
            st.code(_br.format(), language="text")
        except Exception as _ex:  # noqa: BLE001
            st.error(f"ベンチマークに失敗: {_ex}")
    else:
        st.info(f"正解CSVを入れると、現在の拾い出し（{len(items)} 件）との精度を数値化します。")

# ----------------------------- 見積 (F-12) -----------------------------
with tab_est:
    from gopipe_takeoff.estimate import (
        build_estimate,
        write_estimate_excel,
        write_purchase_order_excel,
    )
    from gopipe_takeoff.pricer import Pricer

    overhead = st.slider("諸経費率", 0.0, 0.30, 0.10, 0.01)
    _m = _money_for()
    pricer = Pricer.from_yaml(_kpath("unit_prices.yaml"))
    est = build_estimate(items, pricer, overhead_rate=overhead,
                         tax_rate=_m["tax"], currency_symbol=_m["symbol"])
    _cs = est.currency_symbol

    c1, c2, c3 = st.columns(3)
    c1.metric("小計", f"{_cs}{est.subtotal:,}")
    c2.metric(f"諸経費＋{_m['tax_label']}", f"{_cs}{est.overhead + est.tax:,}")
    c3.metric("合計（税込）", f"{_cs}{est.total:,}")
    c4, c5, c6 = st.columns(3)
    c4.metric("材料費 計", f"{_cs}{est.material_total:,}")
    c5.metric("労務費 計", f"{_cs}{est.labor_total:,}")
    c6.metric("総人工（歩掛）", f"{est.man_hours:g} 人工" if est.man_hours else "—")

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

    st.markdown("##### 🧾 ブランド見積書PDF（提案書級デザイン・そのまま客先提出）")
    pc1, pc2, pc3 = st.columns(3)
    _cli = pc1.text_input("宛先（御中）", "株式会社ハルキ", key="est_client")
    _ven = pc2.text_input("発行者", "株式会社and", key="est_vendor")
    _subj = pc3.text_input("件名", "設備工事一式", key="est_subject")
    if st.button("ブランド見積書PDFを生成", key="est_pdf_gen", type="primary"):
        from gopipe_takeoff.estimate_pdf import build_estimate_pdf

        _today = datetime.date.today()
        _issue = (f"{_today:%B} {_today.day}, {_today.year}" if _loc == "en"
                  else f"{_today.year}年{_today.month}月{_today.day}日")
        _pdfp = build_estimate_pdf(
            est, OUT_DIR / ("Quotation.pdf" if _loc == "en" else "御見積書.pdf"),
            client=_cli, vendor=_ven, subject=_subj,
            issue_date=_issue, tax_label=_m["tax_label"], locale=_loc,
        )
        st.download_button(
            "⬇ 御見積書.pdf をダウンロード", _pdfp.read_bytes(),
            "御見積書.pdf", mime="application/pdf", use_container_width=True, key="est_pdf_dl",
        )
        st.success("ブランド見積書PDFを生成しました。下のボタンで保存できます。")

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
