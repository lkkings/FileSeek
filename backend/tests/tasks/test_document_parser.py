from __future__ import annotations

import zipfile
from pathlib import Path

from fileseek.features.tasks.infrastructure.file_processor.document_parser import (
    DocumentParser,
)


def create_xlsx(path: Path, cell_value: str) -> None:
    main_namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relationship_namespace = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_relationship_namespace = "http://schemas.openxmlformats.org/package/2006/relationships"

    workbook = (
        f'<workbook xmlns="{main_namespace}" xmlns:r="{relationship_namespace}">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    relationships = (
        f'<Relationships xmlns="{package_relationship_namespace}">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    shared_strings = (
        f'<sst xmlns="{main_namespace}" count="1" uniqueCount="1">'
        f'<si><t>{cell_value}</t></si></sst>'
    )
    worksheet = (
        f'<worksheet xmlns="{main_namespace}"><sheetData>'
        '<row r="1"><c r="A1" t="s"><v>0</v></c></row>'
        "</sheetData></worksheet>"
    )

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/sharedStrings.xml", shared_strings)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)


def create_pptx(path: Path, slide_text: str) -> None:
    presentation_namespace = "http://schemas.openxmlformats.org/presentationml/2006/main"
    drawing_namespace = "http://schemas.openxmlformats.org/drawingml/2006/main"
    relationship_namespace = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_relationship_namespace = "http://schemas.openxmlformats.org/package/2006/relationships"

    presentation = (
        f'<p:presentation xmlns:p="{presentation_namespace}" '
        f'xmlns:r="{relationship_namespace}">'
        '<p:sldIdLst><p:sldId id="1" r:id="rId1"/></p:sldIdLst></p:presentation>'
    )
    relationships = (
        f'<Relationships xmlns="{package_relationship_namespace}">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        'Target="slides/slide1.xml"/></Relationships>'
    )
    slide = (
        f'<p:sld xmlns:p="{presentation_namespace}" xmlns:a="{drawing_namespace}">'
        "<p:cSld><p:spTree><p:sp><p:txBody>"
        f"<a:p><a:r><a:t>{slide_text}</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", relationships)
        archive.writestr("ppt/slides/slide1.xml", slide)


def test_document_parser_removes_invalid_characters(tmp_path: Path) -> None:
    file_path = tmp_path / "document.txt"
    file_path.write_bytes(
        b"first\x00 line\xe2\x80\x8b\n\r\nsecond line\tvalue"
        b"\xef\xbb\xbf\xff"
    )

    parsed = DocumentParser().parse_and_chunk(file_path)

    assert parsed.page_count == 1
    assert len(parsed.chunks) == 1
    assert parsed.chunks[0].text == "first line\nsecond line value"
    assert parsed.chunks[0].line_number == 1


def test_document_parser_removes_document_containing_only_invalid_characters(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "document.txt"
    file_path.write_text("\x00\u200b\ufeff\ufffd", encoding="utf-8")

    parsed = DocumentParser().parse_and_chunk(file_path)

    assert parsed.chunks == ()
    assert parsed.page_count == 1


def test_document_parser_extracts_xlsx_shared_strings(tmp_path: Path) -> None:
    file_path = tmp_path / "spreadsheet.xlsx"
    create_xlsx(file_path, "Revenue report")

    parsed = DocumentParser().parse_and_chunk(file_path)

    assert parsed.page_count == 1
    assert [chunk.text for chunk in parsed.chunks] == ["Revenue report"]


def test_document_parser_extracts_pptx_slide_text(tmp_path: Path) -> None:
    file_path = tmp_path / "presentation.pptx"
    create_pptx(file_path, "Quarterly plan")

    parsed = DocumentParser().parse_and_chunk(file_path)

    assert parsed.page_count == 1
    assert [chunk.text for chunk in parsed.chunks] == ["Quarterly plan"]


def test_document_parser_extracts_html_visible_text(tmp_path: Path) -> None:
    file_path = tmp_path / "page.html"
    file_path.write_text(
        "<html><body><h1>Visible title</h1>"
        "<script>hidden()</script></body></html>",
        encoding="utf-8",
    )

    parsed = DocumentParser().parse_and_chunk(file_path)

    assert parsed.page_count == 1
    assert [chunk.text for chunk in parsed.chunks] == ["Visible title"]


def test_document_parser_extracts_csv_rows(tmp_path: Path) -> None:
    file_path = tmp_path / "table.csv"
    file_path.write_text("name,value\nAlpha,1\n", encoding="utf-8")

    parsed = DocumentParser().parse_and_chunk(file_path)

    assert parsed.page_count == 1
    assert [chunk.text for chunk in parsed.chunks] == ["name value\nAlpha 1"]
