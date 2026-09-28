from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ClassifierLabelsDTO:
    document_labels: tuple[str, ...]
    image_labels: tuple[str, ...]
    video_labels: tuple[str, ...]
    version: str


@dataclass(frozen=True)
class StorageLocationDTO:
    id: str
    type: str
    name: str
    protocol: str
    endpoint: str
    root_path: str
    account: str | None
    status: str
    is_system: bool


@dataclass(frozen=True)
class StorageLocationDeletionDTO:
    id: str
    status: str
    affected_files: int


@dataclass(frozen=True)
class ConnectionTestResultDTO:
    success: bool
    message: str


@dataclass(frozen=True)
class StorageDirectoryDTO:
    current_path: str
    entries: tuple[StorageDirectoryEntryDTO, ...]


@dataclass(frozen=True)
class StorageDirectoryEntryDTO:
    name: str
    kind: str
    source_path: str
    size: int
    modified: datetime
