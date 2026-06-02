from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str
    images: list[bytes] = field(default_factory=list)  # PNG/JPEG bytes for vision


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


class LLMClient(Protocol):
    """Provider-agnostic chat interface."""

    name: str

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse: ...
