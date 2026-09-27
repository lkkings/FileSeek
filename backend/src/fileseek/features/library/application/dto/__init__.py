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
