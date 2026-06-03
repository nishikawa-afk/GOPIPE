"""F-13 診断: _dedupe_items の数量潰れ（個数モノ）を GOPIPE で再現確認する。

実 PDF・API キー不要。実 LLM が「同一 spec×同一 location の設備を
個別行（quantity=1 を複数行）で返す」挙動を模した擬似クライアントを使い、
extract() の dedup 経路（two_pass / tile）で総数量が潰れることを示す。

使い方:
  GOPIPE_LLM_PROVIDER=mock python scripts/verify_dedupe_quantity.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from llm_client.base import LLMMessage, LLMResponse  # noqa: E402

from gopipe_takeoff.extractor import _dedupe_items, extract  # noqa: E402
from gopipe_takeoff.models import Drawing, DrawingPage, Tile  # noqa: E402
from gopipe_takeoff.models import TakeoffItem  # noqa: E402

DUMMY_PNG = b"\x89PNG\r\n\x1a\n_dummy_"


def _item(name, spec, qty, unit, loc, conf=0.8) -> TakeoffItem:
    return TakeoffItem(page=1, name=name, spec=spec, quantity=qty, unit=unit, location=loc, confidence=conf)


class ScriptedClient:
    """user メッセージ内容で応答を出し分ける擬似 LLM。

    routes: list of (predicate(content)->bool, json_rows)。最初に一致したものを返す。
    """

    name = "scripted"

    def __init__(self, routes):
        self.model = "scripted"
        self.routes = routes

    def complete(self, messages, *, max_tokens=4096, temperature=0.0) -> LLMResponse:
        content = ""
        for m in messages:
            if m.role == "user":
                content = m.content
        for pred, rows in self.routes:
            if pred(content):
                return LLMResponse(text=json.dumps(rows, ensure_ascii=False), model=self.model)
        return LLMResponse(text="[]", model=self.model)


def _total(items, name):
    return sum(it.quantity for it in items if it.name == name)


def _rows(name, spec, unit, loc, n, qty_each=1, conf=0.8):
    return [
        {"page": 1, "name": name, "spec": spec, "quantity": qty_each, "unit": unit,
         "location": loc, "confidence": conf}
        for _ in range(n)
    ]


def banner(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


# --------------------------------------------------------------------------
# 0. ドメイン真実: _dedupe_items は合算しない（個数モノが潰れる）
# --------------------------------------------------------------------------
banner("0) _dedupe_items の素の挙動（同一 spec×location の個数モノ）")
raw = [
    _item("仕切弁", "GV DN20", 1, "個", "1F PS", conf=0.9),
    _item("仕切弁", "GV DN20", 1, "個", "1F PS", conf=0.7),
    _item("仕切弁", "GV DN20", 1, "個", "1F PS", conf=0.8),
    _item("仕切弁", "GV DN20", 1, "個", "1F PS", conf=0.6),
    _item("仕切弁", "GV DN20", 1, "個", "1F PS", conf=0.5),
]
deduped = _dedupe_items(raw)
print(f"  入力 5 行（実数 5 個） → dedup 後 {len(deduped)} 行 / "
      f"合計 quantity = {_total(deduped, '仕切弁'):g}  （期待 5）")
print("  → 個別行で来た個数モノは confidence 最大の 1 行だけ残り、数量が潰れる。")

# 配管長 m も同様に「潰れる」（合算されない）ことを示す
banner("0b) 配管長 m（系統を跨いだセグメント分割）も合算されない")
raw_m = [
    _item("給水管(SGP)", "VLP DN20", 12.0, "m", "1F 給水系統", conf=0.8),
    _item("給水管(SGP)", "VLP DN20", 16.5, "m", "1F 給水系統", conf=0.6),
]
deduped_m = _dedupe_items(raw_m)
print(f"  入力 2 セグメント（12.0 + 16.5 = 28.5m） → dedup 後 "
      f"{len(deduped_m)} 行 / 合計 = {_total(deduped_m, '給水管(SGP)'):g}m  （期待 28.5）")
print("  → m も keep-one。ただし配管はプロンプトが『系統×口径で1行』を要求するため")
print("    本来 LLM が 1 行で返す設計。問題の主因は個数モノ（個/台/箇所）。")


# --------------------------------------------------------------------------
# 1. two_pass 経路: Pass1 が個別行で返すと Pass1+Pass2 dedup で潰れる
#    ※ 現状 prompts/verification.txt が無く two_pass は inert（Pass2 skip）。
#      ここでは verify prompt を一時的に有効化して line 276 の dedup を再現する。
# --------------------------------------------------------------------------
import gopipe_takeoff.extractor as _ex  # noqa: E402

_ex.VERIFY_PROMPT_PATH = _ex.PROMPT_PATH  # 既存 extraction.txt を verify prompt 代用
banner("1) two_pass 経路で個数モノが潰れる（実 LLM が個別行で返した場合）")
pass1_rows = (
    _rows("仕切弁", "GV DN20", "個", "1F PS", n=5)         # 実数 5 個
    + _rows("90°エルボ", "DN20", "個", "1F 給水系統", n=12)  # 実数 12 個
    + [{"page": 1, "name": "大便器(洋式)", "spec": "TOTO CS232B", "quantity": 2,
        "unit": "台", "location": "1F 便所", "confidence": 0.9}]
)
client = ScriptedClient([
    (lambda c: "追加漏れ確認" in c, []),     # Pass2: 追加なし
    (lambda c: True, pass1_rows),            # Pass1: 個別行
])
page = DrawingPage(page=1, width=1654, height=1169, text="", image_png=DUMMY_PNG, tiles=[])
items = extract(Drawing(source_path="x", pages=[page]), client=client, two_pass=True)
print(f"  仕切弁:   合計 {_total(items, '仕切弁'):g}  （期待 5）")
print(f"  90°エルボ: 合計 {_total(items, '90°エルボ'):g}  （期待 12）")
print(f"  大便器:   合計 {_total(items, '大便器(洋式)'):g}  （期待 2 / 単一行なので保持）")


# --------------------------------------------------------------------------
# 2. tile 経路: 同一 spec×location の個数モノがタイルを跨ぐと潰れる
# --------------------------------------------------------------------------
banner("2) tile 経路で潰れる（タイル内集約しても cross-tile dedup で潰れる）")
# tile0 に弁 3 個, tile1 に弁 2 個（= 実数 5 個）。各タイルが「集約済み 1 行」で返しても…
client_tiles = ScriptedClient([
    (lambda c: "col=0" in c, [{"page": 1, "name": "仕切弁", "spec": "GV DN20",
                               "quantity": 3, "unit": "個", "location": "1F PS", "confidence": 0.8}]),
    (lambda c: "col=1" in c, [{"page": 1, "name": "仕切弁", "spec": "GV DN20",
                               "quantity": 2, "unit": "個", "location": "1F PS", "confidence": 0.7}]),
])
t0 = Tile(image_png=DUMMY_PNG, row=0, col=0, grid=1, width=10, height=10)
t1 = Tile(image_png=DUMMY_PNG, row=0, col=1, grid=1, width=10, height=10)
page_t = DrawingPage(page=1, width=1654, height=1169, text="", image_png=DUMMY_PNG, tiles=[t0, t1])
items_t = extract(Drawing(source_path="x", pages=[page_t]), client=client_tiles, two_pass=False)
print(f"  仕切弁: 合計 {_total(items_t, '仕切弁'):g}  （期待 5 / tile0=3 + tile1=2）")
print("  → タイル単位で集約しても、cross-tile dedup が keep-one するため残留する。")
print("    （プロンプト修正は『1 call 内の集約』までしか効かない＝grid>1 の残課題）")


# --------------------------------------------------------------------------
# 3. 集約規約に従えば（whole-page, 1行/spec×loc）総数量は保持される
# --------------------------------------------------------------------------
banner("3) 集約規約（1 行/spec×location, quantity=個数）なら潰れない【修正の狙い】")
consolidated = [
    {"page": 1, "name": "仕切弁", "spec": "GV DN20", "quantity": 5, "unit": "個",
     "location": "1F PS", "confidence": 0.9},
    {"page": 1, "name": "90°エルボ", "spec": "DN20", "quantity": 12, "unit": "個",
     "location": "1F 給水系統", "confidence": 0.7},
]
client_c = ScriptedClient([
    (lambda c: "追加漏れ確認" in c, []),
    (lambda c: True, consolidated),
])
page_c = DrawingPage(page=1, width=1654, height=1169, text="", image_png=DUMMY_PNG, tiles=[])
items_c = extract(Drawing(source_path="x", pages=[page_c]), client=client_c, two_pass=True)
print(f"  仕切弁:   合計 {_total(items_c, '仕切弁'):g}  （期待 5）")
print(f"  90°エルボ: 合計 {_total(items_c, '90°エルボ'):g}  （期待 12）")
print("  → whole-page では LLM が 1 行で返せば dedup の衝突自体が起きず保持される。")
