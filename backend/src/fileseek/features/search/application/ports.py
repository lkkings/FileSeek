from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from fileseek.features.search.application.dto import AgentAssistantMessage


@dataclass(frozen=True)
class AgentConnection:
    base_url: str
    api_key: str
    model: str


class AgentSettingsProvider(Protocol):
    async def get(self) -> AgentConnection | None: ...


class AgentCompletionClient(Protocol):
    async def complete(
        self,
        messages: Sequence[Mapping[str, object]],
        tools: Sequence[Mapping[str, object]],
    ) -> AgentAssistantMessage: ...
