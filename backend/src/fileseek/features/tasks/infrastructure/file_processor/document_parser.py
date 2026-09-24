"""文档解析与分块服务。

支持 PDF（pypdf）、DOCX（python-docx）、TXT（直接读取）三种格式，
逐页/逐段落提取文本后按目标长度分块，块之间保留重叠以提升检索连续性。
"""

from __future__ import annotations

import re
from pathlib import Path

from fileseek.features.tasks.domain.ports import DocumentParserPort,DocumentChunk,ParsedDocument
from fileseek.features.tasks.domain.exceptions import DocumentParseError, UnsupportedFormatError

_WHITESPACE_RE = re.compile(r"[ \t]+")



def _clean_text(text: str) -> str:
    """去除多余空白，保留段落分隔。"""
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _extract_pdf_pages(file_path: Path) -> list[str]:
    """逐页提取 PDF 文本，返回每页文本列表（索引 0 对应第 1 页）。"""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(file_path))
        return [_clean_text(page.extract_text() or "") for page in reader.pages]
    except (PdfReadError, OSError) as exc:
        msg = f"PDF 解析失败: {file_path}"
        raise DocumentParseError(msg) from exc


def _extract_docx_pages(file_path: Path) -> list[str]:
    """提取 DOCX 段落文本。

    DOCX 没有可靠的页码信息（分页由渲染器决定），因此将全部段落归为“第 1 页”，
    行号按段落顺序编号。
    """
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError

    try:
        document = Document(str(file_path))
        paragraphs = [_clean_text(p.text) for p in document.paragraphs]
        text = "\n".join(p for p in paragraphs if p)
    except (PackageNotFoundError, OSError, KeyError) as exc:
        msg = f"DOCX 解析失败: {file_path}"
        raise DocumentParseError(msg) from exc

    return [text]


def _extract_txt_pages(file_path: Path) -> list[str]:
    """读取 TXT 文件内容，整体作为“第 1 页”。"""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        msg = f"TXT 读取失败: {file_path}"
        raise DocumentParseError(msg) from exc
    return [_clean_text(text)]


_EXTRACTORS = {
    ".pdf": _extract_pdf_pages,
    ".docx": _extract_docx_pages,
    ".txt": _extract_txt_pages,
    ".md": _extract_txt_pages,
}

def _chunk_page_text(
    page_text: str,
    page_number: int,
    chunk_size: int,
    overlap: int,
    start_chunk_index: int = 0,
) -> list[DocumentChunk]:
    """将单页文本按段落优先策略分块。"""

    paragraphs = [p for p in page_text.split("\n") if p]
    if not paragraphs:
        return []

    chunks: list[DocumentChunk] = []
    buffer = ""
    buffer_start_line = 1
    chunk_index = start_chunk_index

    def flush() -> None:
        nonlocal buffer, chunk_index

        if not buffer.strip():
            return

        chunks.append(
            DocumentChunk(
                text=buffer.strip(),
                page_number=page_number,
                line_number=buffer_start_line,
                chunk_index=chunk_index,
            )
        )
        chunk_index += 1
        buffer = ""

    for line_number, paragraph in enumerate(paragraphs, start=1):
        candidate = f"{buffer}\n{paragraph}" if buffer else paragraph

        if len(candidate) <= chunk_size:
            if not buffer:
                buffer_start_line = line_number
            buffer = candidate
            continue

        flush()

        if len(paragraph) <= chunk_size:
            buffer = paragraph
            buffer_start_line = line_number
            continue

        # 单个段落超过 chunk_size，强制切分
        start = 0

        while start < len(paragraph):
            end = min(start + chunk_size, len(paragraph))

            chunks.append(
                DocumentChunk(
                    text=paragraph[start:end].strip(),
                    page_number=page_number,
                    line_number=line_number,
                    chunk_index=chunk_index,
                )
            )

            chunk_index += 1

            if end == len(paragraph):
                break

            start = end - overlap

    flush()

    return chunks

class DocumentParser(DocumentParserPort):
    """文档解析与分块服务。"""

    def parse_and_chunk(
        self,
        file_path: Path,
        chunk_size: int = 400,
        overlap: int = 50,
    ) -> ParsedDocument:
        """解析文档并分块。

        Args:
            file_path: 文档文件路径
            chunk_size: 目标块大小（字符数）
            overlap: 块之间重叠大小（字符数）

        Returns:
            文档块列表，每个元素包含 page_number, line_number, text

        Raises:
            UnsupportedFormatError: 不支持的文档格式
            DocumentParseError: 文档损坏或无法解析
        """
        extractor = _EXTRACTORS.get(file_path.suffix.lower())
        if extractor is None:
            msg = f"不支持的文档格式: {file_path.suffix}"
            raise UnsupportedFormatError(msg)

        pages = extractor(file_path)

        chunks: list[DocumentChunk] = []

        for page_number, page_text in enumerate(pages, start=1):
            page_chunks = _chunk_page_text(
                page_text,
                page_number,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            chunks.extend(page_chunks)

        return ParsedDocument(
            chunks=tuple(chunks),
            page_count=len(pages),
        )
