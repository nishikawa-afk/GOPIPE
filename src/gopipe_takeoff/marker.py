from __future__ import annotations

from pathlib import Path

from .models import TakeoffItem

# カテゴリ→色（RGB 0..1）
COLOR_TABLE = {
    "内装仕上げ": (0.95, 0.30, 0.30),
    "床": (0.30, 0.55, 0.95),
    "設備": (0.30, 0.80, 0.45),
    "建具": (0.95, 0.70, 0.20),
    "外装": (0.65, 0.35, 0.85),
    "その他": (0.55, 0.55, 0.55),
}


def _color_for(category: str | None) -> tuple[float, float, float]:
    return COLOR_TABLE.get(category or "", COLOR_TABLE["その他"])


def write_marker_pdf(
    source_pdf: str | Path,
    items: list[TakeoffItem],
    out_path: str | Path,
    *,
    render_dpi: int = 200,
) -> Path:
    """元 PDF の各ページに bbox + ラベル(名称)を描いた PDF を出力する。

    bbox は render_dpi でレンダリングした画像座標系（左上原点・px）想定。PyMuPDF の
    PDF 座標は左下原点 + ポイント単位なので変換する。
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    import fitz  # PyMuPDF

    doc = fitz.open(source_pdf)
    scale = 72.0 / render_dpi  # px -> pt

    by_page: dict[int, list[TakeoffItem]] = {}
    for it in items:
        if it.bbox is None:
            continue
        by_page.setdefault(it.page, []).append(it)

    for i, page in enumerate(doc, start=1):
        page_h_pt = page.rect.height
        for it in by_page.get(i, []):
            bb = it.bbox
            assert bb is not None
            # px -> pt（PyMuPDF は左上原点 pt なので Y 反転は不要だが、pdf-coord は
            # 左下原点。fitz.Rect は左上原点で扱える）
            r = fitz.Rect(bb.x0 * scale, bb.y0 * scale, bb.x1 * scale, bb.y1 * scale)
            # ページ寸法が PyMuPDF 内では左上原点ポイントなのでそのまま使えるが、
            # レンダリング画像が縦に flip されている PDF の場合は補正が要る。
            # 一般的な図面 PDF はそのまま動く想定で進める。
            color = _color_for(it.category)
            page.draw_rect(r, color=color, width=1.5, fill=None)
            text = f"{it.name} {it.quantity}{it.unit}"
            # ラベル背景
            label_h = 12
            label_rect = fitz.Rect(r.x0, max(r.y0 - label_h - 2, 0), r.x0 + 180, max(r.y0 - 2, label_h))
            page.draw_rect(label_rect, color=color, fill=color)
            page.insert_text(
                (label_rect.x0 + 3, label_rect.y1 - 3),
                text,
                fontsize=8,
                color=(1, 1, 1),
            )
            _ = page_h_pt  # placeholder (将来 Y 反転を入れる際に使う)

    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path
