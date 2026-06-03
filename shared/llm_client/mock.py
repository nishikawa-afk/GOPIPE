from __future__ import annotations

from .base import LLMMessage, LLMResponse


class MockClient:
    """API キー・実 PDF なしでパイプライン疎通を確認するためのモック（配管・設備版）。

    返答は決め打ちの JSON（給排水＋空調の拾い出しサンプル）。入力は無視する。
    name は dictionary.yaml の alias に当たるよう揃えてあるので、classify で
    系統別カテゴリ（給水／給湯／排水／通気／弁類／継手／衛生器具／機器／保温／冷媒）が埋まる。
    """

    name = "mock"

    DEFAULT_TAKEOFF_JSON = """[
      {"page": 1, "name": "給水管(SGP)", "spec": "VLP DN20", "quantity": 28.5, "unit": "m", "location": "1F 給水系統", "confidence": 0.8},
      {"page": 1, "name": "給水管(HIVP)", "spec": "HIVP DN13", "quantity": 15.0, "unit": "m", "location": "1F 給水系統", "confidence": 0.8},
      {"page": 1, "name": "給湯管(被覆銅管)", "spec": "CUP DN15", "quantity": 22.0, "unit": "m", "location": "1F 給湯系統", "confidence": 0.75},
      {"page": 1, "name": "排水管(VP)", "spec": "VP DN50", "quantity": 18.0, "unit": "m", "location": "1F 排水系統", "confidence": 0.8},
      {"page": 1, "name": "通気管(VP)", "spec": "VP DN40", "quantity": 9.0, "unit": "m", "location": "1F 通気系統", "confidence": 0.7},
      {"page": 1, "name": "仕切弁", "spec": "GV DN20", "quantity": 4, "unit": "個", "location": "1F PS", "confidence": 0.9},
      {"page": 1, "name": "90°エルボ", "spec": "DN20", "quantity": 12, "unit": "個", "location": "1F 給水系統", "confidence": 0.6},
      {"page": 1, "name": "大便器(洋式)", "spec": "TOTO CS232B", "quantity": 2, "unit": "台", "location": "1F 便所", "confidence": 0.9},
      {"page": 1, "name": "洗面器", "spec": "LIXIL L-2151", "quantity": 2, "unit": "台", "location": "1F 便所", "confidence": 0.9},
      {"page": 1, "name": "壁掛ガス給湯器", "spec": "RUF-24A", "quantity": 1, "unit": "台", "location": "1F 屋外", "confidence": 0.85},
      {"page": 1, "name": "配管保温(GW20mm)", "spec": "給水管 GW20mm", "quantity": 28.5, "unit": "m", "location": "1F 給水系統", "confidence": 0.7},
      {"page": 1, "name": "冷媒管(ペアコイル)", "spec": "2分3分", "quantity": 16.0, "unit": "m", "location": "1F 空調", "confidence": 0.75},
      {"page": 1, "name": "断熱材(グラスウール)", "spec": "高性能GW16K t90", "quantity": 120.0, "unit": "m2", "location": "外壁", "confidence": 0.8},
      {"page": 1, "name": "押出法ポリスチレンフォーム", "spec": "XPS t50", "quantity": 65.0, "unit": "m2", "location": "1F 床", "confidence": 0.8},
      {"page": 1, "name": "硬質ウレタンフォーム", "spec": "吹付 t30", "quantity": 80.0, "unit": "m2", "location": "屋根", "confidence": 0.75},
      {"page": 1, "name": "防湿気密シート", "spec": "0.2mm", "quantity": 120.0, "unit": "m2", "location": "外壁", "confidence": 0.7},
      {"page": 1, "name": "保温筒", "spec": "GW20mm", "quantity": 28.5, "unit": "m", "location": "1F 給水系統", "confidence": 0.75},
      {"page": 1, "name": "ラッキング", "spec": "アルミ0.3mm", "quantity": 18.0, "unit": "m2", "location": "屋外配管", "confidence": 0.7},
      {"page": 1, "name": "冷温水配管", "spec": "鋼管 80A", "quantity": 45.0, "unit": "m", "location": "1F 空調 氷蓄熱系統", "confidence": 0.8},
      {"page": 1, "name": "圧力計", "spec": "0〜0.6MPa", "quantity": 6, "unit": "個", "location": "1F 機械室", "confidence": 0.85},
      {"page": 1, "name": "電動弁", "spec": "MV 80A", "quantity": 4, "unit": "個", "location": "1F 空調 氷蓄熱系統", "confidence": 0.8},
      {"page": 1, "name": "全熱交換器", "spec": "HEX-1 250型", "quantity": 2, "unit": "台", "location": "1F 各室", "confidence": 0.85}
    ]"""

    def __init__(self, **_: object) -> None:
        self.model = "mock"

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        return LLMResponse(text=self.DEFAULT_TAKEOFF_JSON, model=self.model)
