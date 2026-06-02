from __future__ import annotations

import os

from .base import LLMClient


def get_llm_client(provider: str | None = None) -> LLMClient:
    """`GOPIPE_LLM_PROVIDER` から実装を選ぶ。

    provider: "claude" | "openai" | "mock"
    """
    provider = (provider or os.environ.get("GOPIPE_LLM_PROVIDER") or "claude").lower()

    if provider == "claude":
        from .claude import ClaudeClient

        return ClaudeClient()
    if provider == "openai":
        from .openai import OpenAIClient

        return OpenAIClient()
    if provider == "mock":
        from .mock import MockClient

        return MockClient()
    raise ValueError(f"unknown LLM provider: {provider!r}")
