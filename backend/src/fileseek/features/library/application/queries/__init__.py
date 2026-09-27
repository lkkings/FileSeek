from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListFoldersQuery:
    pass

@dataclass(frozen=True)
class GetFileQuery:
    file_id: str
