from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fileseek.shared.domain.file_types import FileCategory


class FileSortBy(str, Enum):
    RELEVANCE = "relevance"
    CREATED_AT = "created_at"
    SIZE = "size"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True)
class SearchFilesQuery:
    query: str | None

    tag: str | None

    folder_id: str | None

    categories: list[FileCategory] | None

    name_query: str | None = None

    min_size_m: float | None = None

    max_size_m: float | None = None

    start_date: str | None = None

    end_date: str | None = None

    sort_by: FileSortBy = FileSortBy.RELEVANCE
    sort_order: SortOrder = SortOrder.DESC

    page_number: int = 1

    page_size: int = 20


@dataclass(frozen=True)
class EnhancedSearchQuery:
    query: str
    folder_id: str | None
    page_number: int = 1
    page_size: int = 20
    sort_by: FileSortBy = FileSortBy.RELEVANCE
    sort_order: SortOrder = SortOrder.DESC
