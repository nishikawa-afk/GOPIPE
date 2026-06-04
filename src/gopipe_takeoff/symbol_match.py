"""記号テンプレートマッチング（CV・段階2）— numpy NCC ベースのローカル専用ツール。

凡例の記号図形（テンプレート）を図面画像上で正規化相互相関(NCC)により検出して
数える。テキスト層が無いスキャン図でも個数モノを数える狙い（段階1=legend_count
のテキスト版に対する、画像版）。

依存は numpy + Pillow + PyMuPDF のみ（opencv 不要）。
  ・opencv は重く Vercel サーバレスのサイズ上限に響くため API には載せない。
  ・本モジュールはローカル/バッチ前処理として使う想定。

制約（段階2の土台）:
  ・純 numpy のスライディングウィンドウ NCC は大判図面ではメモリ負荷が大きい。
    実運用の高解像度図面では opencv(cv2.matchTemplate, ローカル)か FFT 版へ
    差し替える（インターフェイスは本モジュールのまま）。
  ・しきい値・スケールは実図面ごとの調整が前提。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Match:
    """検出位置（テンプレート左上の座標）とスコア(NCC, -1..1)。"""

    x: int
    y: int
    score: float


def _to_gray(img) -> np.ndarray:
    """PIL.Image / ndarray → 2D float グレースケール。"""
    arr = np.asarray(img, dtype=np.float64)
    if arr.ndim == 3:
        arr = arr[..., :3].mean(axis=2)
    return arr


def ncc_map(image, template) -> np.ndarray:
    """全位置の正規化相互相関(-1..1)マップ。image/template は2D相当。"""
    img = _to_gray(image)
    tpl = _to_gray(template)
    th, tw = tpl.shape
    if img.shape[0] < th or img.shape[1] < tw:
        return np.empty((0, 0))
    windows = np.lib.stride_tricks.sliding_window_view(img, (th, tw))
    w0 = windows - windows.mean(axis=(2, 3), keepdims=True)
    t0 = tpl - tpl.mean()
    num = (w0 * t0).sum(axis=(2, 3))
    denom = np.sqrt((w0 ** 2).sum(axis=(2, 3)) * float((t0 ** 2).sum()))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(denom > 0, num / denom, 0.0)


def find_matches(image, template, *, threshold: float = 0.8, min_distance: int | None = None) -> list[Match]:
    """NCC>=threshold のピークを非極大抑制(NMS)して返す（重複検出を1つに）。"""
    tpl = _to_gray(template)
    th, tw = tpl.shape
    ncc = ncc_map(image, tpl)
    if ncc.size == 0:
        return []
    md = min_distance if min_distance is not None else max(1, max(th, tw) // 2)
    cand = np.argwhere(ncc >= threshold)
    if cand.size == 0:
        return []
    scores = ncc[cand[:, 0], cand[:, 1]]
    occupied = np.zeros(ncc.shape, dtype=bool)
    matches: list[Match] = []
    for idx in np.argsort(-scores):
        y, x = int(cand[idx, 0]), int(cand[idx, 1])
        if occupied[y, x]:
            continue
        matches.append(Match(x=x, y=y, score=float(ncc[y, x])))
        occupied[max(0, y - md):y + md + 1, max(0, x - md):x + md + 1] = True
    return matches


def count_matches(image, template, *, threshold: float = 0.8, scales: tuple[float, ...] = (1.0,)) -> int:
    """記号の個数。複数スケールを試し、最も多く一致したスケールの件数を返す。"""
    from PIL import Image

    best = 0
    base = _to_gray(template)
    for s in scales:
        if s == 1.0:
            tpl = base
        else:
            im = Image.fromarray(base.astype(np.uint8))
            tpl = _to_gray(im.resize((max(1, int(im.width * s)), max(1, int(im.height * s)))))
        best = max(best, len(find_matches(image, tpl, threshold=threshold)))
    return best


def page_image(pdf_path: str, *, page_index: int = 0, dpi: int = 150) -> np.ndarray:
    """PDFの1ページを画像(ndarray, H×W×C)にレンダリング（スキャン図のCV入力用）。"""
    import fitz

    doc = fitz.open(pdf_path)
    pix = doc[page_index].get_pixmap(dpi=dpi)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    doc.close()
    return arr
