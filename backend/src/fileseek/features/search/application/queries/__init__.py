from __future__ import annotations

from dataclasses import dataclass

from fileseek.shared.domain.file_types import FileType


@dataclass(frozen=True)
class SearchFilesQuery:
    query: str
    file_types: list[FileType] | None
    limit: int
    name_query: str | None = None
    min_size_m: float | None = None
    max_size_m: float | None = None
    start_date: str | None = None
    end_date: str | None = None
