from __future__ import annotations

from pathlib import Path
from typing import Protocol
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentChunk:
    """文档中的一个文本块。"""

    text: str
    page_number: int | None = None
    line_number: int | None = None
    chunk_index: int = 0


@dataclass(frozen=True)
class ParsedDocument:
    """解析后的完整文档。"""

    chunks: tuple[DocumentChunk, ...]
    page_count: int


class DocumentParserPort(Protocol):
    def parse_and_chunk(self, path: Path) -> ParsedDocument: ...
