"""ブランド見積書PDF（提案書級デザイン）。

reportlab ＋ 日本語TTF で、ネイビー×オレンジの体裁の御見積書を生成する。
明細（カテゴリ別）＋ 内訳（材料費/労務費/総人工/諸経費内訳/消費税/合計）。
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .estimate import Estimate

NAVY = colors.HexColor("#14304F")
ACC = colors.HexColor("#E8833A")
LIGHT = colors.HexColor("#F2F5F9")
GREY = colors.HexColor("#6B7280")
LINEC = colors.HexColor("#D8DEE9")

_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]


def _font() -> str:
    for p in _FONTS:
        if Path(p).exists():
            try:
                pdfmetrics.registerFont(TTFont("JP", p))
                return "JP"
            except Exception:  # noqa: BLE001
                continue
    return "Helvetica"


def _money(n: float, symbol: str = "¥") -> str:
    return f"{symbol}{int(round(n)):,}"


def build_estimate_pdf(
    estimate: Estimate,
    out_path: str | Path,
    *,
    client: str = "",
    vendor: str = "",
    subject: str = "設備工事一式",
    issue_date: str = "",
    tax_label: str = "消費税",
) -> Path:
    """見積から御見積書PDFを生成して out_path に保存する。"""
    f = _font()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sym = estimate.currency_symbol or "¥"
    _y = partial(_money, symbol=sym)

    body = ParagraphStyle("b", fontName=f, fontSize=9, leading=12, textColor=NAVY)
    small = ParagraphStyle("s", fontName=f, fontSize=8, leading=11, textColor=GREY)
    rcell = ParagraphStyle("r", fontName=f, fontSize=9, leading=12, textColor=NAVY, alignment=2)
    title = ParagraphStyle("t", fontName=f, fontSize=24, leading=28, textColor=NAVY, alignment=1)

    story: list = []
    story.append(Paragraph("御 見 積 書", title))
    story.append(Spacer(1, 2))
    # オレンジのアクセント線
    rule = Table([[""]], colWidths=[166 * mm], rowHeights=[2.4])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACC)]))
    story.append(rule)
    story.append(Spacer(1, 10))

    # 宛先（左） / 発行者・発行日（右）
    left = [
        Paragraph(f"<b>{client or '　'} 御中</b>", ParagraphStyle("c", fontName=f, fontSize=13, textColor=NAVY)),
        Spacer(1, 4),
        Paragraph(f"件名：{subject}", body),
        Paragraph("下記のとおり御見積申し上げます。", small),
    ]
    right = [
        Paragraph(f"発行日：{issue_date or '　　　年　　月　　日'}", rcell),
        Spacer(1, 2),
        Paragraph(f"{vendor or '　'}", rcell),
        Paragraph("登録番号 T________________", small),
    ]
    head = Table([[left, right]], colWidths=[100 * mm, 66 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(head)
    story.append(Spacer(1, 10))

    # ご請求金額（税込）の大箱
    total_box = Table(
        [[Paragraph("お見積金額（税込）", ParagraphStyle("tl", fontName=f, fontSize=11, textColor=colors.white)),
          Paragraph(_y(estimate.total), ParagraphStyle("tv", fontName=f, fontSize=20, textColor=colors.white, alignment=2))]],
        colWidths=[83 * mm, 83 * mm],
    )
    total_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(total_box)
    story.append(Spacer(1, 12))

    # 明細（カテゴリ別）
    rows = [["No", "カテゴリ", "名称", "仕様", "数量", "単位", "単価", "金額"]]
    lines = sorted(estimate.lines, key=lambda ln: (ln.item.category or "zzz", ln.item.name))
    for i, ln in enumerate(lines, start=1):
        rows.append([
            str(i), ln.item.category or "", Paragraph(ln.item.name, body),
            Paragraph(ln.item.spec or "", small), f"{ln.item.quantity:g}", ln.item.unit or "",
            _y(ln.unit_price), _y(ln.amount),
        ])
    tbl = Table(rows, colWidths=[9 * mm, 18 * mm, 46 * mm, 33 * mm, 14 * mm, 10 * mm, 18 * mm, 18 * mm], repeatRows=1)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), f), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"), ("ALIGN", (0, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TEXTCOLOR", (0, 1), (-1, -1), NAVY),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINEC), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for r in range(1, len(rows), 2):
        style.append(("BACKGROUND", (0, r), (-1, r), LIGHT))
    tbl.setStyle(TableStyle(style))
    story.append(tbl)
    story.append(Spacer(1, 10))

    # 内訳（右寄せの小表）
    mh = f"{estimate.man_hours:g} 人工" if estimate.man_hours else "—"
    brk = [
        ["材料費 計", _y(estimate.material_total)],
        ["労務費 計", _y(estimate.labor_total)],
        ["（総人工）", mh],
        ["小計", _y(estimate.subtotal)],
        [f"現場管理費", _y(estimate.site_overhead)],
        [f"一般管理費", _y(estimate.general_overhead)],
        [f"{tax_label}（{estimate.tax_rate:.0%}）", _y(estimate.tax)],
        ["合計（税込）", _y(estimate.total)],
    ]
    bt = Table(brk, colWidths=[40 * mm, 40 * mm], hAlign="RIGHT")
    bt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), f), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), NAVY), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINEC),
        ("BACKGROUND", (0, -1), (-1, -1), NAVY), ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(bt)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "・本見積の有効期限は発行日より30日間です。・数量はAI拾い出し＋人確認に基づく概算で、"
        "最終確認のうえ確定します。・記載の単価・歩掛は社内標準であり、現場条件により調整します。", small))

    SimpleDocTemplate(
        str(out_path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=18 * mm, bottomMargin=16 * mm, title="御見積書",
    ).build(story)
    return out_path
