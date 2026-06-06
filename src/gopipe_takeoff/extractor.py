from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path

from llm_client import LLMClient, LLMMessage, get_llm_client

from .equipment_table import extract_from_text
from .locale import resolve as resolve_knowledge
from .models import BBox, Drawing, DrawingPage, TakeoffItem, Tile

logger = logging.getLogger("gopipe.extractor")

PROMPT_PATH        = Path(__file__).resolve().parents[2] / "prompts" / "extraction.txt"
VERIFY_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "verification.txt"
LEGEND_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "legend.txt"

# Claude の vision 呼び出しで一度に返せる JSON 件数上限を考慮した値
DEFAULT_MAX_TOKENS    = 8192   # v1 は 4096 だったが A1 密度の高い図面で途中切れが発生
VERIFY_MAX_TOKENS     = 4096

# テキスト層から記号コードを抽出する正規表現 (例: EI2-GR06, GR01, P02, LA04, SOK-A)
_SYMBOL_CODE_RE = re.compile(r"\b([A-Z]{1,4}[0-9]{1,2}[-_]?[A-Z0-9]{0,4})\b")


def _load_prompt(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _strip_code_fence(text: str) -> str:
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    return m.group(1) if m else text


def _parse_response(raw: str, *, page_number: int, drop_bbox: bool = False) -> list[TakeoffItem]:
    """LLM レスポンスの JSON を TakeoffItem のリストにする。"""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    items: list[TakeoffItem] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            bbox_val = None if drop_bbox else row.get("bbox")
            items.append(
                TakeoffItem(
                    page=row.get("page", page_number),
                    name=row.get("name", ""),
                    spec=row.get("spec"),
                    quantity=float(row.get("quantity", 0) or 0),
                    unit=row.get("unit", ""),
                    location=row.get("location"),
                    bbox=BBox.from_list(bbox_val) if bbox_val else None,
                    confidence=float(row.get("confidence", 1.0) or 1.0),
                )
            )
        except Exception:
            continue
    return items


def _call_llm_for_image(
    client: LLMClient,
    system_prompt: str,
    *,
    image_png: bytes | None,
    user_text: str,
    page_number: int,
    drop_bbox: bool = False,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[TakeoffItem]:
    """1 画像 + ユーザーテキストで LLM を呼んで TakeoffItem のリストを返す。"""
    msgs = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(
            role="user",
            content=user_text,
            images=[image_png] if image_png else [],
        ),
    ]
    resp = client.complete(msgs, max_tokens=max_tokens, temperature=0.0)
    raw = _strip_code_fence(resp.text).strip()
    return _parse_response(raw, page_number=page_number, drop_bbox=drop_bbox)


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return unicodedata.normalize("NFKC", s).replace(" ", "").replace("　", "").lower()


def _dedupe_items(items: list[TakeoffItem]) -> list[TakeoffItem]:
    """タイル間や Pass1/Pass2 間で重複した項目を除去する。

    優先キー:
      1. spec が非空: (spec, location)
      2. spec なし   : (category, name, location)

    重複時は confidence が高い方を残す（同点なら先勝ち）。
    """
    by_key: dict[tuple, TakeoffItem] = {}
    order: list[tuple] = []
    for it in items:
        loc = _norm(it.location)
        if it.spec and it.spec.strip():
            key: tuple = ("spec", _norm(it.spec), loc)
        else:
            key = ("catname", _norm(it.category), _norm(it.name), loc)
        cur = by_key.get(key)
        if cur is None:
            by_key[key] = it
            order.append(key)
            continue
        if it.confidence > cur.confidence:
            by_key[key] = it
    return [by_key[k] for k in order]


def _qty_close(a: float, b: float, tol: float = 0.05) -> bool:
    hi = max(abs(a), abs(b))
    return True if hi == 0 else abs(a - b) / hi <= tol


def _spec_match(a: str | None, b: str | None) -> bool:
    """型番/口径の一致。完全一致 or 3文字以上の包含（'DN20'⊂'GV DN20' 等）。"""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    return len(min(na, nb, key=len)) >= 3 and (na in nb or nb in na)


def _find_table_match(items: list[TakeoffItem], ti: TakeoffItem) -> TakeoffItem | None:
    """機器表行 ti に対応する vision 抽出項目を探す（spec 一致優先、無ければ name 一致）。"""
    if ti.spec and _norm(ti.spec):
        for it in items:
            if _spec_match(it.spec, ti.spec):
                return it
    tn = _norm(ti.name)
    if tn:
        for it in items:
            inm = _norm(it.name)
            if inm and (inm == tn or (len(inm) >= 3 and inm in tn)):
                return it
    return None


def reconcile_with_text_table(
    vision_items: list[TakeoffItem], page_text: str, *, page: int = 1,
) -> list[TakeoffItem]:
    """テキスト層の機器表（確定情報）で vision 抽出を補正・補完する。

    ベクター(CAD)PDF はテキスト層に台数・型番・口径が「文字」で入っているため、
    画像認識より正確。本処理は:
      - 機器表に対応する vision 項目があれば数量・型番を機器表優先で採用し、
        信頼度を引き上げる（数量ズレは警告ログ）。
      - vision に無い機器表項目は「拾い漏れ」として追加する。
      - テキスト層が無い（画像 PDF）場合は vision をそのまま返す（フォールバック）。
    """
    table_items = extract_from_text(page_text or "", page=page)
    if not table_items:
        return vision_items

    result = list(vision_items)
    matched = mismatched = added = 0
    for ti in table_items:
        m = _find_table_match(result, ti)
        if m is None:
            ti.source = "text_table"
            result.append(ti)
            added += 1
            continue
        matched += 1
        if not _qty_close(m.quantity, ti.quantity):
            logger.warning(
                "page %d: 数量ズレ '%s' vision=%s 機器表=%s → 機器表を採用",
                page, m.name, m.quantity, ti.quantity,
            )
            mismatched += 1
        m.quantity = ti.quantity
        if ti.spec and not (m.spec and m.spec.strip()):
            m.spec = ti.spec
        m.confidence = max(m.confidence, 0.95)
        m.source = "reconciled"
    logger.info(
        "page %d: 機器表突合 matched=%d (ズレ%d) added=%d", page, matched, mismatched, added
    )
    return result


def _extract_symbol_codes(text: str) -> list[str]:
    """テキスト層から図面記号コードを抽出する（例: EI2-GR06, GR01, SOK-A 等）。"""
    if not text:
        return []
    codes = sorted(set(_SYMBOL_CODE_RE.findall(text)))
    # 一般的な英単語 (THE, AND, NOT 等) はフィルタ
    _stop = {"AND", "NOT", "THE", "FOR", "ALL", "NEW", "OLD", "TOP", "PER", "ROW", "COL"}
    return [c for c in codes if c not in _stop and len(c) >= 2]


def _tile_user_text(page: DrawingPage, tile: Tile, symbol_codes: list[str]) -> str:
    """タイル抽出時のユーザーテキスト。タイル位置と記号コードを Claude に明示する。"""
    codes_hint = ""
    if symbol_codes:
        codes_hint = (
            f"\nテキスト層で検出した記号コード（これらを図面上で探してください）: "
            f"{', '.join(symbol_codes[:40])}"
        )
    return (
        f"## ページ {page.page}（{tile.grid}×{tile.grid} 分割の row={tile.row}, col={tile.col} タイル）\n"
        f"このタイル領域から拾い出し項目を JSON 配列で返してください。\n"
        f"タイル境界で半分しか見えない部材は、可能なら spec から推測して 1 行で出してください "
        f"（次のタイルでも同じ部材を出した場合は後段で重複除去します）。\n"
        f"テキスト層 (ページ全体): {(page.text or '(なし)')[:2000]}"
        f"{codes_hint}"
    )


def _whole_page_user_text(page: DrawingPage, symbol_codes: list[str]) -> str:
    codes_hint = ""
    if symbol_codes:
        codes_hint = (
            f"\n\n## テキスト層で検出した記号コード（これらを図面上で必ず探す）\n"
            f"{', '.join(symbol_codes[:60])}\n"
            f"上記コードが図面に描かれていれば、対応する部材を行に起こしてください。"
        )
    return (
        f"## ページ {page.page}\n"
        f"このページから拾い出し項目を JSON 配列で返してください。\n"
        f"テキスト層（機器表・数量表があれば最優先で使う）: {page.text[:8000] if page.text else '(なし)'}"
        f"{codes_hint}"
    )


def _verification_user_text(
    page: DrawingPage,
    existing_items: list[TakeoffItem],
    symbol_codes: list[str],
) -> str:
    """Pass2 (verification) 用のユーザーテキスト。既抽出リストを渡す。"""
    existing_summary = "\n".join(
        f"  - {it.name} / spec={it.spec or '-'} / loc={it.location or '-'}"
        for it in existing_items[:60]
    )
    codes_hint = ""
    if symbol_codes:
        # Pass2 では特に未抽出のコードに絞る
        extracted_specs = {_norm(it.spec) for it in existing_items if it.spec}
        missing_codes = [c for c in symbol_codes if _norm(c) not in extracted_specs]
        if missing_codes:
            codes_hint = (
                f"\n\n## まだ抽出されていないテキスト層の記号コード（重点確認）\n"
                f"{', '.join(missing_codes[:40])}"
            )
    return (
        f"## ページ {page.page} — 追加漏れ確認\n\n"
        f"### すでに抽出済みの項目（これらは出力しない）:\n"
        f"{existing_summary or '  (なし)'}\n"
        f"{codes_hint}\n\n"
        f"上記リストに**載っていない**部材を図面から探して JSON 配列で返してください。\n"
        f"テキスト層: {page.text[:2000] if page.text else '(なし)'}"
    )


def extract(
    drawing: Drawing,
    *,
    client: LLMClient | None = None,
    two_pass: bool = False,
    use_text_table: bool = True,
) -> list[TakeoffItem]:
    """各ページを LLM に投げて TakeoffItem のリストを返す。

    two_pass=True のとき:
      Pass1: 通常の拾い出し
      Pass2: Pass1 の結果を見せた上で「漏れがないか」確認する verification pass
      両者を dedup してマージ。

    DrawingPage に tiles が乗っていれば、各タイルを個別に LLM 呼び出しし、
    最後に spec / (cat,name) で重複除去する。タイル分割時の bbox は無視する。
    画像も tile も無いページはテキストのみで投げる（フォールバック）。

    use_text_table=True のとき、各ページのテキスト層(機器表/数量表)から確定情報を
    抽出し、vision 結果と突合する（数量・型番を機器表優先で採用、拾い漏れを補完）。
    """
    client = client or get_llm_client()
    system_prompt = _load_prompt(resolve_knowledge("extraction.txt"))
    verify_prompt  = _load_prompt(resolve_knowledge("verification.txt")) if two_pass else ""
    all_items: list[TakeoffItem] = []

    for page in drawing.pages:
        symbol_codes = _extract_symbol_codes(page.text or "")
        if symbol_codes:
            logger.info("page %d: %d symbol codes detected in text layer", page.page, len(symbol_codes))

        # ---- Pass 1: 通常抽出 ----
        if page.tiles:
            tile_items: list[TakeoffItem] = []
            for tile in page.tiles:
                logger.info(
                    "page %d: extracting tile (r=%d, c=%d) of %dx%d",
                    page.page, tile.row, tile.col, tile.grid, tile.grid,
                )
                tile_items.extend(
                    _call_llm_for_image(
                        client,
                        system_prompt,
                        image_png=tile.image_png,
                        user_text=_tile_user_text(page, tile, symbol_codes),
                        page_number=page.page,
                        drop_bbox=True,
                    )
                )
            before = len(tile_items)
            page_items = _dedupe_items(tile_items)
            logger.info("page %d: pass1 deduped %d → %d items", page.page, before, len(page_items))
        else:
            page_items = _call_llm_for_image(
                client,
                system_prompt,
                image_png=page.image_png,
                user_text=_whole_page_user_text(page, symbol_codes),
                page_number=page.page,
                drop_bbox=False,
            )
            logger.info("page %d: pass1 extracted %d items", page.page, len(page_items))

        # ---- Pass 2: Verification (two_pass=True のみ) ----
        if two_pass and verify_prompt and page.image_png:
            logger.info("page %d: running verification pass ...", page.page)
            extra_items = _call_llm_for_image(
                client,
                verify_prompt,
                image_png=page.image_png,
                user_text=_verification_user_text(page, page_items, symbol_codes),
                page_number=page.page,
                drop_bbox=False,
                max_tokens=VERIFY_MAX_TOKENS,
            )
            logger.info("page %d: verification pass found %d additional items", page.page, len(extra_items))
            combined = page_items + extra_items
            before = len(combined)
            page_items = _dedupe_items(combined)
            logger.info("page %d: after dedup %d → %d items", page.page, before, len(page_items))

        # ---- 機器表テキスト層との突合（確定情報を優先）----
        if use_text_table:
            before = len(page_items)
            page_items = reconcile_with_text_table(page_items, page.text or "", page=page.page)
            if len(page_items) != before:
                logger.info(
                    "page %d: 機器表突合で %d → %d items", page.page, before, len(page_items)
                )

        all_items.extend(page_items)

    return all_items
