from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FolderDTO:
    id: str
    name: str
    icon_type: str
    description: str
    modified: str
    file_count: int

@dataclass(frozen=True)
class FileDTO:
    id: str
    name: str
    file_type: str
    category: str
    size: int
    modified: str
    path: str
    folder_id: str | None
    tags: list[str]


@dataclass(frozen=True)
class FileThumbnailDTO:
    id: str
    size: str
    data: bytes
    source_size: int
    source_modified: str


@dataclass(frozen=True)
class FileAvailabilityDTO:
    id: str
    access_state: str
    last_checked_at: str


@dataclass(frozen=True)
class AddFileResult:
    file_id: str
    task_id: str


@dataclass(frozen=True)
class BatchImportStartedDTO:
    import_id: str
    total: int


@dataclass(frozen=True)
class ImportEventDTO:
    id: int
    type: str
    payload: dict[str, object]


@dataclass(frozen=True)
class ImportTaskSnapshotDTO:
    task_id: str
    file_id: str | None
    status: str
    progress: int
    stage: str | None
    error_message: str | None
