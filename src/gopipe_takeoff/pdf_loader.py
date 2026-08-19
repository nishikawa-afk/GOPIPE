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

# ここを下回る DPI まで落ちたページは、そのまま送っても表の小さい文字が潰れて読めない。
# 実測(2026-08-19 ハルキ実図面): A3 200dpi のスキャンは 112dpi まで落ち、
# 図面に印刷された吹出口/吸込口表(12行22個)を 1 個も拾えず、存在しない記号まで出した。
# 同じ図面を 3x3 タイル(各300dpi)にすると 12行22個が完全一致・確度0.9 になった。
# → 落ちたページは自動でタイルに切り替える（呼び出し側の指定は不要）。
AUTO_TILE_MIN_DPI = 150
# 1 リクエストあたりの LLM 呼び出し数の上限（サーバレスの実行時間 300 秒を守るため）。
AUTO_TILE_MAX_CALLS = 9


def _enhance_png(data: bytes) -> bytes:
    """スキャン画像向けの軽い前処理（自動コントラスト＋鮮鋭化）。

    小さな数字・記号をAIが読みやすくする。失敗時や非対応環境では原画像を返す
    （PIL のみ・依存追加なし）。ベクター描画には適用しない（呼び出し側で判定）。
    """
    try:
        import io

        from PIL import Image, ImageEnhance, ImageFilter, ImageOps

        im = Image.open(io.BytesIO(data)).convert("RGB")
        im = ImageOps.autocontrast(im, cutoff=1)
        im = ImageEnhance.Contrast(im).enhance(1.3)
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=130, threshold=2))
        out = io.BytesIO()
        im.save(out, format="PNG")
        return out.getvalue()
    except Exception:  # noqa: BLE001
        return data


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


def _render_tiles(page, *, grid: int, dpi: int, enhance: bool = False) -> list[Tile]:
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
            if enhance:
                _e = _enhance_png(data)
                if len(_e) <= MAX_IMAGE_BYTES:
                    data = _e
            logger.info(
                "page %d tile (r=%d, c=%d) rendered at %d dpi (%dx%d px, %.1f KB)",
                page.number + 1, row, col, used_dpi, w, h, len(data) / 1024,
            )
            tiles.append(
                Tile(image_png=data, row=row, col=col, grid=grid, width=w, height=h)
            )
    return tiles


def auto_grid(used_dpi: int, *, tile_dpi: int = DEFAULT_TILE_DPI, page_count: int = 1) -> int:
    """縮小されて読めなくなったページを、何分割にすれば読めるかを返す（1 なら分割しない）。

    - 目標 DPI に届く最小の分割数を選ぶ（面積比で byte 上限に収まる）
    - 1 リクエストの LLM 呼び出しを AUTO_TILE_MAX_CALLS 以下に抑える（実行時間 300 秒の壁）
    """
    import math

    if used_dpi >= AUTO_TILE_MIN_DPI:
        return 1
    need = math.ceil(tile_dpi / max(used_dpi, 1))
    budget = math.isqrt(max(AUTO_TILE_MAX_CALLS // max(page_count, 1), 1))
    return max(1, min(need, budget))


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
        page_count = doc.page_count
        for i, page in enumerate(doc, start=1):
            data, w, h, used_dpi = _render_pixmap_within_limit(page, dpi=dpi)
            if used_dpi != dpi:
                logger.info("page %d rendered at %d dpi (downscaled from %d)", i, used_dpi, dpi)
            text = page.get_text("text") or ""
            is_scan = len(text.strip()) < 50  # テキスト層が薄い=スキャン画像とみなす
            if is_scan:
                _enh = _enhance_png(data)
                if len(_enh) <= MAX_IMAGE_BYTES:
                    data = _enh
                    logger.info("page %d: scan detected → image enhanced (contrast+sharpen)", i)
            tiles: list[Tile] = []
            page_grid = grid
            if page_grid <= 1 and used_dpi < AUTO_TILE_MIN_DPI:
                # 縮小されて読めなくなったページだけ、自動でタイルに切り替える
                page_grid = auto_grid(used_dpi, tile_dpi=tile_dpi, page_count=page_count)
                if page_grid > 1:
                    logger.info(
                        "page %d: %ddpi まで縮小されたため自動でタイル分割に切替 (grid=%d)",
                        i, used_dpi, page_grid,
                    )
                else:
                    logger.warning(
                        "page %d: %ddpi まで縮小されたが、ページ数が多いためタイル分割を見送り"
                        "（表の数量が読めない可能性が高い）", i, used_dpi,
                    )
            if page_grid > 1:
                logger.info("page %d: rendering %dx%d tiles at %d dpi", i, page_grid, page_grid, tile_dpi)
                tiles = _render_tiles(page, grid=page_grid, dpi=tile_dpi, enhance=is_scan)
            pages.append(
                DrawingPage(
                    page=i, width=w, height=h, text=text, image_png=data, tiles=tiles,
                )
            )
        doc.close()
    else:
        pages.append(DrawingPage(page=1, width=1654, height=1169, text=""))

    return Drawing(source_path=str(path), pages=pages)
