from __future__ import annotations

from dataclasses import dataclass

from fileseek.features.tasks.domain.ports import IndexedFileMetadata


@dataclass(frozen=True)
class TaskDTO:
    id: str
    source_path: str
    status: str
    progress: int
    stage: str | None
    error_message: str | None
    created_at: str


@dataclass(frozen=True)
class TaskListDTO:
    tasks: list[TaskDTO]
    total: int
    counts: dict[str, int]
