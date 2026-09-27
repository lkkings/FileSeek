from dataclasses import dataclass


@dataclass(frozen=True)
class FileDTO:
    id: str
    name: str
    path: str
    size: int
    file_type: str
    modified: str


@dataclass(frozen=True)
class TaskDTO:
    id: str
    file: FileDTO
    status: str
    progress: int
    stage: str | None
    error_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TaskListDTO:
    tasks: list[TaskDTO]
    total: int
    counts: dict[str, int]