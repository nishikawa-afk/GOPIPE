"""F-13: 個数モノの数量潰れ回帰テスト。

背景: extractor._dedupe_items は同一キー（spec×location 等）の項目を
1 行に統合する際、confidence 最大の 1 行だけ残し **数量を合算しない**。
これはタイル間／Pass 間で「同じ部材」が二重に来たときの正しい挙動だが、
LLM が「同一種別×同一場所の設備」を個別行（quantity=1 を複数行）で返すと
数量が実数より小さく潰れる。

対策は prompts/extraction.txt 側で「同一 name×spec×location は 1 行に集約し
quantity に合計を入れる」と明示すること（dedup 本体は触らない）。本テストは:
  1) dedup が合算しない不変条件（プロンプトが集約を担う前提）
  2) 集約規約に従えば extract() で総数量が保持されること
  3) prompts/extraction.txt に集約ルールが入っていること
を固定する。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from llm_client.base import LLMResponse  # noqa: E402

from gopipe_takeoff.extractor import _dedupe_items, extract  # noqa: E402
from gopipe_takeoff.models import Drawing, DrawingPage, TakeoffItem, Tile  # noqa: E402

DUMMY_PNG = b"\x89PNG\r\n\x1a\n_dummy_"


def _item(name, spec, qty, unit, loc, conf=0.8) -> TakeoffItem:
    return TakeoffItem(
        page=1, name=name, spec=spec, quantity=qty, unit=unit, location=loc, confidence=conf
    )


class ScriptedClient:
    """user メッセージ内容で応答を出し分ける擬似 LLM。"""

    name = "scripted"

    def __init__(self, routes):
        self.model = "scripted"
        self.routes = routes

    def complete(self, messages, *, max_tokens=4096, temperature=0.0) -> LLMResponse:
        content = next((m.content for m in messages if m.role == "user"), "")
        for pred, rows in self.routes:
            if pred(content):
                return LLMResponse(text=json.dumps(rows, ensure_ascii=False), model=self.model)
        return LLMResponse(text="[]", model=self.model)


def _total(items, name):
    return sum(it.quantity for it in items if it.name == name)


# --------------------------------------------------------------------------
# 1. 不変条件: dedup は同一キーを合算しない（個数モノ／長さモノとも keep-one）
# --------------------------------------------------------------------------
def test_dedupe_keeps_one_and_does_not_sum_count_items():
    """同一 spec×location の弁が 5 個別行で来ると 1 行・quantity=最大conf行 になる。"""
    rows = [
        _item("仕切弁", "GV DN20", 1, "個", "1F PS", conf=0.5),
        _item("仕切弁", "GV DN20", 1, "個", "1F PS", conf=0.9),  # 最大 conf
        _item("仕切弁", "GV DN20", 1, "個", "1F PS", conf=0.7),
        _item("仕切弁", "GV DN20", 1, "個", "1F PS", conf=0.6),
        _item("仕切弁", "GV DN20", 1, "個", "1F PS", conf=0.8),
    ]
    deduped = _dedupe_items(rows)
    assert len(deduped) == 1
    # 合算されない＝5 ではなく 1。これがプロンプト側集約を必要とする理由。
    assert _total(deduped, "仕切弁") == 1


def test_dedupe_does_not_sum_pipe_length_segments():
    """同一系統×管種×口径の配管を 2 区間で返すと延長が合算されず潰れる。"""
    rows = [
        _item("給水管(SGP)", "VLP DN20", 12.0, "m", "1F 給水系統", conf=0.8),
        _item("給水管(SGP)", "VLP DN20", 16.5, "m", "1F 給水系統", conf=0.6),
    ]
    deduped = _dedupe_items(rows)
    assert len(deduped) == 1
    assert _total(deduped, "給水管(SGP)") == 12.0  # 28.5 ではない


def test_dedupe_keeps_distinct_specs_and_locations_separate():
    """口径・系統・階が違えば別行のまま（過剰統合しない）。"""
    rows = [
        _item("仕切弁", "GV DN20", 3, "個", "1F PS"),
        _item("仕切弁", "GV DN13", 2, "個", "1F PS"),     # 口径違い → 別行
        _item("仕切弁", "GV DN20", 1, "個", "2F PS"),     # 階違い → 別行
    ]
    deduped = _dedupe_items(rows)
    assert len(deduped) == 3
    assert _total(deduped, "仕切弁") == 6


# --------------------------------------------------------------------------
# 2. 契約: LLM が集約規約に従えば extract() で総数量が保持される
# --------------------------------------------------------------------------
def test_consolidated_rows_preserve_total_through_tile_extract():
    """各タイルが『1 行/種別・quantity=個数』で返し、別物は別キーなら保持される。"""
    client = ScriptedClient([
        (lambda c: "col=0" in c, [
            {"page": 1, "name": "仕切弁", "spec": "GV DN20", "quantity": 3,
             "unit": "個", "location": "1F PS", "confidence": 0.8},
        ]),
        # 別タイルは別系統の別部材（別キー）→ dedup で消えない
        (lambda c: "col=1" in c, [
            {"page": 1, "name": "90°エルボ", "spec": "DN20", "quantity": 7,
             "unit": "個", "location": "1F 給水系統", "confidence": 0.8},
        ]),
    ])
    t0 = Tile(image_png=DUMMY_PNG, row=0, col=0, grid=1, width=10, height=10)
    t1 = Tile(image_png=DUMMY_PNG, row=0, col=1, grid=1, width=10, height=10)
    page = DrawingPage(page=1, width=100, height=100, text="", image_png=DUMMY_PNG, tiles=[t0, t1])
    items = extract(Drawing(source_path="x", pages=[page]), client=client, two_pass=False)
    assert _total(items, "仕切弁") == 3
    assert _total(items, "90°エルボ") == 7


def test_per_instance_rows_still_collapse_across_tiles():
    """残課題の固定: 同一キーの個数モノがタイルを跨ぐと cross-tile dedup で潰れる。

    プロンプト集約は『1 call 内』までしか効かない。grid>=2 で同一 spec×location が
    複数タイルに散ると依然 keep-one になる（既定 grid=1 では発生しない）。
    """
    client = ScriptedClient([
        (lambda c: "col=0" in c, [
            {"page": 1, "name": "仕切弁", "spec": "GV DN20", "quantity": 3,
             "unit": "個", "location": "1F PS", "confidence": 0.8},
        ]),
        (lambda c: "col=1" in c, [
            {"page": 1, "name": "仕切弁", "spec": "GV DN20", "quantity": 2,
             "unit": "個", "location": "1F PS", "confidence": 0.7},
        ]),
    ])
    t0 = Tile(image_png=DUMMY_PNG, row=0, col=0, grid=1, width=10, height=10)
    t1 = Tile(image_png=DUMMY_PNG, row=0, col=1, grid=1, width=10, height=10)
    page = DrawingPage(page=1, width=100, height=100, text="", image_png=DUMMY_PNG, tiles=[t0, t1])
    items = extract(Drawing(source_path="x", pages=[page]), client=client, two_pass=False)
    # 実数 5 だが cross-tile dedup で 3（最大 conf 行）に潰れる＝既知の残課題。
    assert _total(items, "仕切弁") == 3


# --------------------------------------------------------------------------
# 3. プロンプトに集約ルールが入っていること（誤って削除されないよう固定）
# --------------------------------------------------------------------------
def test_extraction_prompt_has_consolidation_rule():
    text = (ROOT / "prompts" / "extraction.txt").read_text(encoding="utf-8")
    assert "数量の集約" in text
    assert "1 行" in text
    # 単位ごとの扱い（個数は数える／長さは合算）が明示されていること
    assert "個数を数えて" in text
    assert "合算" in text
