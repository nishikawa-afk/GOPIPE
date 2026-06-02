from __future__ import annotations

from .dictionary import TakeoffDictionary
from .models import TakeoffItem


def classify(items: list[TakeoffItem], dictionary: TakeoffDictionary) -> list[TakeoffItem]:
    """辞書ベースで category を埋める。ヒットしなければ 'その他'。

    Side-effect ではなく新しいリストを返す。
    """
    out: list[TakeoffItem] = []
    for it in items:
        entry = dictionary.lookup(it.name)
        if entry is not None:
            out.append(
                it.model_copy(
                    update={
                        "category": entry.category,
                        "name": entry.canonical,
                        "unit": it.unit or entry.unit,
                    }
                )
            )
        else:
            out.append(it.model_copy(update={"category": "その他"}))
    return out
