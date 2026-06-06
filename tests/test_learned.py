"""学習の堀（修正→辞書自動成長）のテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "shared"))

from gopipe_takeoff.classifier import classify  # noqa: E402
from gopipe_takeoff.dictionary import TakeoffDictionary  # noqa: E402
from gopipe_takeoff.learned import load_aliases, record_alias  # noqa: E402
from gopipe_takeoff.models import TakeoffItem  # noqa: E402

DICT = ROOT / "prompts" / "dictionary.yaml"


def test_record_and_load(tmp_path):
    p = tmp_path / "learned.json"
    assert record_alias("全熱交換ユニット", "全熱交換器", category="機器", unit="台", path=p)
    assert not record_alias("同じ", "同じ", path=p)        # 変化なしは学習しない
    a = load_aliases(p)
    assert "全熱交換ユニット" in a
    assert a["全熱交換ユニット"]["canonical"] == "全熱交換器"


def test_learned_alias_improves_classification():
    # 未登録の表記ゆれを学習させると、分類が その他 → 正規名/カテゴリ になる
    raw = "ZZUNKNOWNITEMZZ"   # 辞書に無い・部分一致もしない表記
    d = TakeoffDictionary.from_yaml(DICT)
    before = classify([TakeoffItem(page=1, name=raw, quantity=1, unit="台")], d)
    assert before[0].category == "その他"

    d2 = TakeoffDictionary.from_yaml(DICT)
    d2.add_learned({raw: {"canonical": "全熱交換器", "category": "機器", "unit": "台", "raw": raw}})
    after = classify([TakeoffItem(page=1, name=raw, quantity=1, unit="台")], d2)
    assert after[0].name == "全熱交換器"
    assert after[0].category != "その他"


def test_load_aliases_remote_safe_when_supabase_off(tmp_path):
    # Supabase 未設定でも remote=True で落ちず、ローカルJSONを返す
    p = tmp_path / "l.json"
    record_alias("生表記X", "給水管", category="給水", unit="m", path=p)
    a = load_aliases(p, remote=True)
    assert "生表記X" in a and a["生表記X"]["canonical"] == "給水管"


def test_add_learned_creates_entry_for_unknown_canonical():
    d = TakeoffDictionary.from_yaml(DICT)
    d.add_learned({"謎部材A": {"canonical": "特注金物", "category": "雑材", "unit": "個", "raw": "謎部材A"}})
    out = classify([TakeoffItem(page=1, name="謎部材A", quantity=2, unit="個")], d)
    assert out[0].name == "特注金物" and out[0].category == "雑材"
