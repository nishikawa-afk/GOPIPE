from __future__ import annotations

import base64
import os

from .base import LLMMessage, LLMResponse


class ClaudeClient:
    name = "claude"

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        # Lazy import so the package is optional at import-time.
        from anthropic import Anthropic

        self._client = Anthropic(api_key=self.api_key)

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        system_parts = [m.content for m in messages if m.role == "system"]
        chat = [m for m in messages if m.role != "system"]

        anth_messages = []
        for m in chat:
            content: list[dict] = [{"type": "text", "text": m.content}]
            for img in m.images:
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(img).decode("ascii"),
                        },
                    }
                )
            anth_messages.append({"role": m.role, "content": content})

        # Claude Opus 4.7 など最新モデルは temperature 引数が deprecated。
        # 必要なときだけ渡す（呼び出し側が明示的に非デフォルト値を渡した場合）。
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": anth_messages,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        # 古いモデル向けの後方互換: 0 以外なら一応渡す。エラーなら無視する想定。
        if temperature and temperature != 0.0:
            kwargs["temperature"] = temperature
        resp = self._client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return LLMResponse(
            text=text,
            model=self.model,
            usage={
                "input_tokens": getattr(resp.usage, "input_tokens", 0),
                "output_tokens": getattr(resp.usage, "output_tokens", 0),
            },
        )
