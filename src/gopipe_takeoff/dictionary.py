from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# 社内で使う標準カテゴリ。ここに無いカテゴリは warning（運用次第で追加 OK）。
STANDARD_CATEGORIES = (
    # --- 配管 系統別 ---
    "給水",
    "給湯",
    "排水",
    "通気",
    "消火",
    "ガス",
    "冷媒",
    "冷温水",
    "ドレン",
    # --- 部材・器具・機器 ---
    "弁類",
    "継手",
    "計装",
    "衛生器具",
    "機器",
    "ダクト",
    # --- 付帯工事 ---
    "保温",
    "支持金物",
    "はつり・復旧",
    "試験調整",
    "雑材",
    # --- 断熱・気密（建築断熱） ---
    "断熱材",
    "気密防湿",
    # --- 海外展開(en)カテゴリ / VISION.md ---
    "HVAC",
    "Equipment",
    "Piping",
    "Duct",
    "Valve",
    "Insulation",
    # --- どこにも当てはまらないとき ---
    "その他",
)

# 標準単位。ここに無い単位は warning。
STANDARD_UNITS = ("m2", "m", "式", "箇所", "枚", "面", "台", "本", "個", "kg", "t", "ea", "ft", "lf")

# classifier の部分一致しきい値（< だと事実上無視される）
MIN_ALIAS_LENGTH_FOR_PARTIAL_MATCH = 3


def norm_key(s: str | None) -> str:
    """辞書の鍵を突き合わせるための正規化。

    learned.py 側の保存時と同じ規則（NFKC・空白除去）にそろえる。ここがズレると
    「覚えたのに引けない」が静かに起きる。
    """
    return unicodedata.normalize("NFKC", (s or "").strip()).replace(" ", "").replace("　", "")


@dataclass
class DictionaryEntry:
    canonical: str
    category: str
    unit: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # "error" | "warning"
    canonical: str | None
    message: str

    def __str__(self) -> str:
        prefix = f"[{self.severity.upper()}]"
        if self.canonical:
            return f"{prefix} {self.canonical}: {self.message}"
        return f"{prefix} {self.message}"


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    def format(self) -> str:
        if not self.issues:
            return "✓ 辞書は妥当です。問題なし。"
        lines = []
        if self.errors:
            lines.append(f"エラー: {len(self.errors)} 件")
            for i in self.errors:
                lines.append(f"  {i}")
        if self.warnings:
            lines.append(f"警告: {len(self.warnings)} 件")
            for i in self.warnings:
                lines.append(f"  {i}")
        return "\n".join(lines)


class DictionaryValidationError(ValueError):
    """strict ロード時、エラーがあると投げる。"""

    def __init__(self, result: ValidationResult) -> None:
        self.result = result
        super().__init__(result.format())


def validate(entries: list[DictionaryEntry]) -> ValidationResult:
    """辞書エントリの整合性をチェックする。errors と warnings を返す。"""
    result = ValidationResult()

    seen_canonicals: dict[str, int] = {}
    alias_to_canonical: dict[str, str] = {}

    for idx, e in enumerate(entries):
        # 必須フィールド
        if not e.canonical or not e.canonical.strip():
            result.issues.append(
                ValidationIssue(
                    "error", None, f"entries[{idx}]: canonical が空です"
                )
            )
            continue
        if not e.category or not e.category.strip():
            result.issues.append(
                ValidationIssue("error", e.canonical, "category が空です")
            )
        if not e.unit or not e.unit.strip():
            result.issues.append(
                ValidationIssue("error", e.canonical, "unit が空です")
            )

        # canonical 重複
        if e.canonical in seen_canonicals:
            result.issues.append(
                ValidationIssue(
                    "error",
                    e.canonical,
                    f"canonical が重複しています (entries[{seen_canonicals[e.canonical]}] と entries[{idx}])",
                )
            )
        else:
            seen_canonicals[e.canonical] = idx

        # category / unit が標準集合に無いなら warning
        if e.category and e.category not in STANDARD_CATEGORIES:
            result.issues.append(
                ValidationIssue(
                    "warning",
                    e.canonical,
                    f"category '{e.category}' は標準カテゴリ {STANDARD_CATEGORIES} にありません",
                )
            )
        if e.unit and e.unit not in STANDARD_UNITS:
            result.issues.append(
                ValidationIssue(
                    "warning",
                    e.canonical,
                    f"unit '{e.unit}' は標準単位 {STANDARD_UNITS} にありません",
                )
            )

        # aliases チェック
        seen_local_aliases: set[str] = set()
        for a in e.aliases:
            if not a or not a.strip():
                result.issues.append(
                    ValidationIssue("error", e.canonical, "空文字の alias があります")
                )
                continue
            if a == e.canonical:
                result.issues.append(
                    ValidationIssue(
                        "warning",
                        e.canonical,
                        f"alias '{a}' が canonical と同一です（冗長）",
                    )
                )
            if a in seen_local_aliases:
                result.issues.append(
                    ValidationIssue(
                        "warning",
                        e.canonical,
                        f"alias '{a}' がエントリ内で重複しています",
                    )
                )
            seen_local_aliases.add(a)
            if len(a) < MIN_ALIAS_LENGTH_FOR_PARTIAL_MATCH:
                result.issues.append(
                    ValidationIssue(
                        "warning",
                        e.canonical,
                        f"alias '{a}' は {MIN_ALIAS_LENGTH_FOR_PARTIAL_MATCH} 文字未満で、部分一致では拾われません",
                    )
                )
            if a in alias_to_canonical and alias_to_canonical[a] != e.canonical:
                result.issues.append(
                    ValidationIssue(
                        "error",
                        e.canonical,
                        f"alias '{a}' が他エントリ '{alias_to_canonical[a]}' でも使われています（マッチング曖昧）",
                    )
                )
            alias_to_canonical[a] = e.canonical

    # 別エントリの canonical と被る alias を検出
    canonical_set = set(seen_canonicals.keys())
    for e in entries:
        for a in e.aliases:
            if a in canonical_set and a != e.canonical:
                result.issues.append(
                    ValidationIssue(
                        "error",
                        e.canonical,
                        f"alias '{a}' は別エントリの canonical と衝突します",
                    )
                )

    return result


class TakeoffDictionary:
    """社内辞書: 名称ゆれを正規化 + カテゴリ/単位を付与する。"""

    def __init__(self, entries: list[DictionaryEntry]) -> None:
        self.entries = entries
        self._index: dict[str, DictionaryEntry] = {}
        # 会社が育てた索引は組み込みと必ず分けて持つ。混ぜると、学習が組み込みの
        # エントリを乗っ取り「2種類目を教えた瞬間に1種類目が化ける」事故になる。
        self._learned_index: dict[str, DictionaryEntry] = {}
        for e in entries:
            self._put(self._index, e.canonical, e)
            for a in e.aliases:
                self._put(self._index, a, e)

    @staticmethod
    def _put(index: dict, key: str, entry: DictionaryEntry) -> None:
        k = norm_key(key)
        if k:
            index[k] = entry

    def _partial(self, index: dict, name: str) -> DictionaryEntry | None:
        """部分一致。最長の鍵を勝たせる（「水管」より「給水管」を採る）。"""
        best_key = ""
        best: DictionaryEntry | None = None
        for key, entry in index.items():
            if len(key) >= MIN_ALIAS_LENGTH_FOR_PARTIAL_MATCH and key in name and len(key) > len(best_key):
                best_key, best = key, entry
        return best

    def resolve(self, name: str) -> tuple[DictionaryEntry | None, bool]:
        """(エントリ, 完全一致だったか) を返す。

        探索順は 会社の学習(完全) → 組み込み(完全) → 会社の学習(部分) → 組み込み(部分)。
        完全一致でないときに名称を正規名へ書き換えると、AIが正しく読んだ名前
        （例: 「逆止弁 DN20」）を別部材の名前に化けさせるので、呼び出し側が
        判断できるよう「完全一致だったか」を返す。
        """
        n = norm_key(name)
        if not n:
            return None, False
        if n in self._learned_index:
            return self._learned_index[n], True
        if n in self._index:
            return self._index[n], True
        hit = self._partial(self._learned_index, n)
        if hit is not None:
            return hit, False
        return self._partial(self._index, n), False

    def lookup(self, name: str) -> DictionaryEntry | None:
        return self.resolve(name)[0]

    def add_learned(self, aliases: dict) -> int:
        """学習済み別名 {raw: {canonical, category, unit, raw}} を辞書に統合する。

        raw（＝AIが実際に読んだ生の名称）だけを会社側の索引に入れる。組み込みの
        索引には一切触らない。触ると「仕切弁→バタフライ弁」を教えた瞬間に、
        図面上の本物の仕切弁まで全部バタフライ弁に化ける。
        """
        n = 0
        for raw, info in (aliases or {}).items():
            info = info or {}
            canon = str(info.get("canonical") or raw).strip()
            if not raw or not canon:
                continue
            base, _exact = self.resolve(canon)
            entry = DictionaryEntry(
                canonical=canon,
                category=(info.get("category") or (base.category if base else "その他")),
                unit=(info.get("unit") or (base.unit if base else "")),
                aliases=(),
            )
            self.entries.append(entry)
            self._put(self._learned_index, raw, entry)
            _orig = info.get("raw")
            if _orig:
                self._put(self._learned_index, str(_orig), entry)
            # 会社が選んだ呼び方そのものも引けるようにする（次回そのまま出るように）
            self._put(self._learned_index, canon, entry)
            n += 1
        return n

    @classmethod
    def from_yaml(cls, path: str | Path, *, strict: bool = True) -> TakeoffDictionary:
        """YAML から辞書を読み込む。

        strict=True（デフォルト）: errors があれば DictionaryValidationError を投げる。
        strict=False: errors があっても黙って読み込む（CI 以外でデバッグしたい時用）。
        どちらの場合も警告は標準ロガーで通知。
        """
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries: list[DictionaryEntry] = []
        for idx, row in enumerate(data.get("entries", [])):
            if not isinstance(row, dict):
                raise DictionaryValidationError(
                    ValidationResult(
                        issues=[
                            ValidationIssue(
                                "error",
                                None,
                                f"entries[{idx}] が dict ではありません: {type(row).__name__}",
                            )
                        ]
                    )
                )
            try:
                entries.append(
                    DictionaryEntry(
                        canonical=row["canonical"],
                        category=row["category"],
                        unit=row.get("unit", ""),
                        aliases=tuple(row.get("aliases", [])),
                    )
                )
            except KeyError as e:
                raise DictionaryValidationError(
                    ValidationResult(
                        issues=[
                            ValidationIssue(
                                "error",
                                row.get("canonical"),
                                f"必須フィールド {e.args[0]!r} が無い (entries[{idx}])",
                            )
                        ]
                    )
                ) from None

        result = validate(entries)
        if strict and result.has_errors:
            raise DictionaryValidationError(result)
        if result.warnings:
            import logging

            logger = logging.getLogger("gopipe.dictionary")
            for w in result.warnings:
                logger.warning(str(w))
        return cls(entries)
