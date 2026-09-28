from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListFoldersQuery:
    pass

@dataclass(frozen=True)
class GetFileQuery:
    file_id: str


@dataclass(frozen=True)
class GetFileThumbnailQuery:
    file_id: str
    size: str


@dataclass(frozen=True)
class CheckFileAvailabilityQuery:
    file_id: str
