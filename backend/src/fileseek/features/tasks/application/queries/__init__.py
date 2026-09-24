from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListTasksQuery:
    status: str | None
    page: int
    page_size: int


@dataclass(frozen=True)
class GetTaskQuery:
    task_id: str
