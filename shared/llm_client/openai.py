from __future__ import annotations

import base64
import os

from .base import LLMMessage, LLMResponse


class OpenAIClient:
    name = "openai"

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        from openai import OpenAI

        self._client = OpenAI(api_key=self.api_key)

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        oai_messages = []
        for m in messages:
            content: list[dict] | str
            if m.images:
                content = [{"type": "text", "text": m.content}]
                for img in m.images:
                    b64 = base64.b64encode(img).decode("ascii")
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        }
                    )
            else:
                content = m.content
            oai_messages.append({"role": m.role, "content": content})

        resp = self._client.chat.completions.create(
            model=self.model,
            messages=oai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = resp.choices[0]
        return LLMResponse(
            text=choice.message.content or "",
            model=self.model,
            usage={
                "input_tokens": getattr(resp.usage, "prompt_tokens", 0),
                "output_tokens": getattr(resp.usage, "completion_tokens", 0),
            },
        )
