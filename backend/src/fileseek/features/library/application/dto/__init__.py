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
    size: int
    modified: str
    path: str
    parent_folder: str | None


@dataclass(frozen=True)
class RecycleItemDTO:
    id: str
    original_file_id: str
    original_name: str
    original_path: str
    deleted_at: str
    file_type: str
    size: int


@dataclass(frozen=True)
class RecentAccessDTO:
    file_id: str
    accessed_at: str
