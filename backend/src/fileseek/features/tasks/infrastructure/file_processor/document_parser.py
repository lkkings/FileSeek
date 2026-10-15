"""文档解析与分块服务。

支持 PDF、DOCX、XLSX、PPTX、HTML、CSV 和文本类格式，
逐页/逐段落提取文本后按目标长度分块，块之间保留重叠以提升检索连续性。
"""

from __future__ import annotations

import csv
import re
import unicodedata
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from defusedxml.ElementTree import fromstring as parse_xml

from fileseek.features.tasks.domain.exceptions import DocumentParseError, UnsupportedFormatError
from fileseek.features.tasks.domain.ports import DocumentChunk, DocumentParserPort, ParsedDocument

_WHITESPACE_RE = re.compile(r"[ \t]+")

_REPLACEMENT_CHARACTER = "\ufffd"

_MAIN_XML_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_PRESENTATION_XML_NAMESPACE = "http://schemas.openxmlformats.org/presentationml/2006/main"
_DRAWING_XML_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/main"
_RELATIONSHIP_XML_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_RELATIONSHIP_XML_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"


def _remove_invalid_characters(text: str) -> str:
    """移除控制字符、格式字符、无效码位和替换占位符。"""
    return "".join(
        character
        for character in text
        if character == "\t"
        or (
            not unicodedata.category(character).startswith("C")
            and character != _REPLACEMENT_CHARACTER
        )
    )


def _clean_text(text: str) -> str:
    """去除多余空白，保留段落分隔。"""
    lines = [
        _WHITESPACE_RE.sub(" ", _remove_invalid_characters(line)).strip()
        for line in text.splitlines()
    ]
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


def _normalize_relationship_target(relationship_path: str, target: str) -> str:
    if target.startswith("/"):
        return target.removeprefix("/")

    source_directory = Path(relationship_path).parent.parent
    return (source_directory / target).as_posix()


def _ordered_relationship_targets(
    archive: zipfile.ZipFile,
    relationship_path: str,
    relationship_ids: list[str],
) -> list[str]:
    relationships = parse_xml(archive.read(relationship_path))
    requested_ids = set(relationship_ids)
    targets: list[str] = []

    for relationship in relationships.findall(
        f"{{{_PACKAGE_RELATIONSHIP_XML_NAMESPACE}}}Relationship"
    ):
        relationship_id = relationship.attrib.get("Id", "")
        if relationship_id not in requested_ids:
            continue
        target = relationship.attrib.get("Target", "")
        targets.append(_normalize_relationship_target(relationship_path, target))

    return targets


def _extract_xlsx_pages(file_path: Path) -> list[str]:
    """按工作表顺序提取 XLSX 单元格文本。"""
    namespace = f"{{{_MAIN_XML_NAMESPACE}}}"

    try:
        with zipfile.ZipFile(file_path) as archive:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared_root = parse_xml(archive.read("xl/sharedStrings.xml"))
                shared_strings = [
                    "".join(text.text or "" for text in item.iter(f"{namespace}t"))
                    for item in shared_root.findall(f"{namespace}si")
                ]

            workbook = parse_xml(archive.read("xl/workbook.xml"))
            relationship_ids = [
                sheet.attrib.get(f"{{{_RELATIONSHIP_XML_NAMESPACE}}}id", "")
                for sheet in workbook.findall(f"{namespace}sheets/{namespace}sheet")
            ]
            sheet_targets = _ordered_relationship_targets(
                archive,
                "xl/_rels/workbook.xml.rels",
                relationship_ids,
            )

            pages: list[str] = []
            for sheet_target in sheet_targets:
                sheet = parse_xml(archive.read(sheet_target))
                lines: list[str] = []

                for row in sheet.findall(f"{namespace}sheetData/{namespace}row"):
                    cells = [
                        _xlsx_cell_text(cell, shared_strings)
                        for cell in row.findall(f"{namespace}c")
                    ]
                    line = "\t".join(cell for cell in cells if cell)
                    if line:
                        lines.append(line)

                pages.append(_clean_text("\n".join(lines)))

            return pages or [""]
    except (
        OSError,
        zipfile.BadZipFile,
        ElementTree.ParseError,
        KeyError,
        ValueError,
        IndexError,
    ) as exc:
        msg = f"XLSX 解析失败: {file_path}"
        raise DocumentParseError(msg) from exc


def _xlsx_cell_text(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    namespace = f"{{{_MAIN_XML_NAMESPACE}}}"
    cell_type = cell.attrib.get("t", "")

    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(f"{namespace}t"))

    value = cell.find(f"{namespace}v")
    if value is None or value.text is None:
        return ""

    if cell_type == "s":
        return shared_strings[int(value.text)]

    return value.text


def _extract_pptx_pages(file_path: Path) -> list[str]:
    """按幻灯片顺序提取 PPTX 文本。"""
    presentation_namespace = f"{{{_PRESENTATION_XML_NAMESPACE}}}"
    drawing_namespace = f"{{{_DRAWING_XML_NAMESPACE}}}"

    try:
        with zipfile.ZipFile(file_path) as archive:
            presentation = parse_xml(archive.read("ppt/presentation.xml"))
            relationship_ids = [
                slide_id.attrib.get(f"{{{_RELATIONSHIP_XML_NAMESPACE}}}id", "")
                for slide_id in presentation.findall(
                    f"{presentation_namespace}sldIdLst/{presentation_namespace}sldId"
                )
            ]
            slide_targets = _ordered_relationship_targets(
                archive,
                "ppt/_rels/presentation.xml.rels",
                relationship_ids,
            )

            pages: list[str] = []
            for slide_target in slide_targets:
                slide = parse_xml(archive.read(slide_target))
                lines: list[str] = []

                for paragraph in slide.iter(f"{drawing_namespace}p"):
                    text = "".join(
                        text_node.text or ""
                        for text_node in paragraph.iter(f"{drawing_namespace}t")
                    )
                    if text:
                        lines.append(text)

                pages.append(_clean_text("\n".join(lines)))

            return pages or [""]
    except (
        OSError,
        zipfile.BadZipFile,
        ElementTree.ParseError,
        KeyError,
        ValueError,
        IndexError,
    ) as exc:
        msg = f"PPTX 解析失败: {file_path}"
        raise DocumentParseError(msg) from exc


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skipped_depth = 0
        self._lines: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        _ = attrs
        if tag in {"script", "style", "template"}:
            self._skipped_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template"} and self._skipped_depth:
            self._skipped_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skipped_depth:
            self._lines.append(data)

    def text(self) -> str:
        return "\n".join(line for line in self._lines if line.strip())


def _extract_html_pages(file_path: Path) -> list[str]:
    """提取 HTML 可见文本。"""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        msg = f"HTML 读取失败: {file_path}"
        raise DocumentParseError(msg) from exc

    extractor = _HTMLTextExtractor()
    extractor.feed(text)
    extractor.close()
    return [_clean_text(extractor.text())]


def _extract_csv_pages(file_path: Path) -> list[str]:
    """提取 CSV 每行文本。"""
    try:
        with file_path.open(encoding="utf-8", errors="replace", newline="") as csv_file:
            rows = csv.reader(csv_file)
            lines = ["\t".join(cell for cell in row if cell) for row in rows]
    except (OSError, csv.Error) as exc:
        msg = f"CSV 解析失败: {file_path}"
        raise DocumentParseError(msg) from exc

    return [_clean_text("\n".join(line for line in lines if line))]


_EXTRACTORS = {
    ".pdf": _extract_pdf_pages,
    ".docx": _extract_docx_pages,
    ".txt": _extract_txt_pages,
    ".md": _extract_txt_pages,
    ".xlsx": _extract_xlsx_pages,
    ".pptx": _extract_pptx_pages,
    ".html": _extract_html_pages,
    ".htm": _extract_html_pages,
    ".csv": _extract_csv_pages,
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

    def __init__(self, chunk_size: int = 4096, overlap: int = 256) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def parse_and_chunk(self, file_path: Path) -> ParsedDocument:
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
                chunk_size=self.chunk_size,
                overlap=self.overlap,
            )

            chunks.extend(page_chunks)

        return ParsedDocument(
            chunks=tuple(chunks),
            page_count=len(pages),
        )
