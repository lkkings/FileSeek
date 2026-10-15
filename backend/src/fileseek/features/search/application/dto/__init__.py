from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class FileDTO:
    """向量命中的文件基础信息。"""

    file_id: str
    file_name: str
    file_type: str
    category: str
    path: str
    size: int | None
    modified: str | None
    tags: list[str]
    score: float = 0
    metadata: dict[str, object] = field(default_factory=dict)
    chunks: list[object] = field(default_factory=list)


@dataclass(frozen=True)
class SearchResultsDTO:
    items: list[FileDTO]
    counter: dict[str, int]
    total: int = 0
    page_number: int = 1
    page_size: int = 20


@dataclass(frozen=True)
class AgentToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class AgentAssistantMessage:
    content: str | None
    tool_calls: tuple[AgentToolCall, ...]


@dataclass(frozen=True)
class EnhancedSearchProgressDTO:
    """Round-level progress emitted while a retrieval-augmented search runs."""

    type: Literal[
        "status",
        "reasoning",
        "tool_call",
        "tool_result",
        "result",
        "error",
    ]
    phase: str | None = None
    message: str | None = None
    round_number: int | None = None
    content: str | None = None
    tool_name: str | None = None
    query: str | None = None
    categories: tuple[str, ...] = ()
    name_query: str | None = None
    candidate_count: int | None = None
    total: int | None = None
    result: SearchResultsDTO | None = None
    error: str | None = None
