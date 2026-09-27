from __future__ import annotations

from dataclasses import dataclass
@dataclass(frozen=True)
class FileDTO:
    """向量命中的文件基础信息。"""

    file_id: str
    file_name: str
    file_type: str
    category: str
    path: str
    size: int | None
    modified: str | None
    tags: list[str]
    score: float = 0
    metadata: dict = None
    chunks: list = None

@dataclass(frozen=True)
class SearchResultsDTO:
    items: list[FileDTO]
    counter: dict[str,int]
    total: int = 0
    page_number: int = 1
    page_size: int = 20
