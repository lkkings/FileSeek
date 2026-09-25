from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListFoldersQuery:
    pass

@dataclass(frozen=True)
class ListFilesQuery:
    folder_name: str | None
    file_type: str | None
    page: int
    page_size: int

@dataclass(frozen=True)
class GetFileQuery:
    file_id: str
