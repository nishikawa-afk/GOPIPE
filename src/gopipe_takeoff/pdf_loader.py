from __future__ import annotations

import logging
from pathlib import Path

from .models import Drawing, DrawingPage, Tile

logger = logging.getLogger("gopipe.pdf_loader")

DEFAULT_DPI = 200
# Claude の image size 上限 (5 MB) に収めるための画像 byte 上限。
# 余裕を見て 4.5 MB に。超えたら DPI を段階的に下げて再レンダリング。
MAX_IMAGE_BYTES = 4_500_000
MIN_DPI = 72
# タイル分割時の初期 DPI。タイル化により 1 タイルあたりの面積は減るので
# DPI を上げても 5MB 制限に収まりやすい (細部が見えやすくなる)。
DEFAULT_TILE_DPI = 300


def _render_pixmap_within_limit(
    page, *, dpi: int, clip=None
) -> tuple[bytes, int, int, int]:
    """指定 DPI でレンダリング（clip 指定で領域限定可）し、画像サイズ上限を
    超えたら DPI を下げて再試行する。

    Returns: (png_bytes, width, height, used_dpi)
    """
    import fitz  # PyMuPDF

    cur_dpi = dpi
    last_data: bytes | None = None
    last_w = last_h = 0
    while cur_dpi >= MIN_DPI:
        zoom = cur_dpi / 72.0
        kwargs = {"matrix": fitz.Matrix(zoom, zoom), "alpha": False}
        if clip is not None:
            kwargs["clip"] = clip
        pix = page.get_pixmap(**kwargs)
        data = pix.tobytes("png")
        last_data, last_w, last_h = data, pix.width, pix.height
        if len(data) <= MAX_IMAGE_BYTES:
            return data, pix.width, pix.height, cur_dpi
        logger.warning(
            "page %d image %.1f MB > %.1f MB at %ddpi, lowering",
            page.number + 1, len(data) / 1_048_576, MAX_IMAGE_BYTES / 1_048_576, cur_dpi,
        )
        new_dpi = max(MIN_DPI, int(cur_dpi * 0.75))
        if new_dpi == cur_dpi:  # 既に MIN_DPI なら抜ける
            break
        cur_dpi = new_dpi
    return last_data or b"", last_w, last_h, cur_dpi


def _render_tiles(page, *, grid: int, dpi: int) -> list[Tile]:
    """ページを N×N グリッドに切り、各タイルを個別レンダリングする。"""
    import fitz  # PyMuPDF

    rect = page.rect  # pt
    tw = rect.width / grid
    th = rect.height / grid
    tiles: list[Tile] = []
    for row in range(grid):
        for col in range(grid):
            clip = fitz.Rect(col * tw, row * th, (col + 1) * tw, (row + 1) * th)
            data, w, h, used_dpi = _render_pixmap_within_limit(page, dpi=dpi, clip=clip)
            logger.info(
                "page %d tile (r=%d, c=%d) rendered at %d dpi (%dx%d px, %.1f KB)",
                page.number + 1, row, col, used_dpi, w, h, len(data) / 1024,
            )
            tiles.append(
                Tile(image_png=data, row=row, col=col, grid=grid, width=w, height=h)
            )
    return tiles


def load_pdf(
    path: str | Path,
    *,
    dpi: int = DEFAULT_DPI,
    grid: int = 1,
    tile_dpi: int = DEFAULT_TILE_DPI,
) -> Drawing:
    """PDF をページ単位でレンダリング（PNG bytes）+ テキスト抽出して返す。

    PyMuPDF（fitz）が無い環境ではテキスト抽出のみ・画像 None でフォールバック。
    画像サイズが Claude の 5 MB 上限を超える場合は DPI を自動で段階的に下げる。

    grid > 1 のときは、各ページを grid×grid のタイルに分割して別々にレンダリング
    する（vision LLM が細部を読みやすくなる代わりに API コストは grid^2 倍）。
    フルページ画像 image_png も残す（マーカー描画用）。
    """
    path = Path(path)
    pages: list[DrawingPage] = []

    try:
        import fitz  # PyMuPDF
    except Exception:
        fitz = None

    if fitz is not None and path.exists():
        doc = fitz.open(path)
        for i, page in enumerate(doc, start=1):
            data, w, h, used_dpi = _render_pixmap_within_limit(page, dpi=dpi)
            if used_dpi != dpi:
                logger.info("page %d rendered at %d dpi (downscaled from %d)", i, used_dpi, dpi)
            tiles: list[Tile] = []
            if grid > 1:
                logger.info("page %d: rendering %dx%d tiles at %d dpi", i, grid, grid, tile_dpi)
                tiles = _render_tiles(page, grid=grid, dpi=tile_dpi)
            pages.append(
                DrawingPage(
                    page=i,
                    width=w,
                    height=h,
                    text=page.get_text("text") or "",
                    image_png=data,
                    tiles=tiles,
                )
            )
        doc.close()
    else:
        pages.append(DrawingPage(page=1, width=1654, height=1169, text=""))

    return Drawing(source_path=str(path), pages=pages)
