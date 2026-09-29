from __future__ import annotations

from fileseek.shared.domain.file_types import FileType
from fileseek.shared.utils.file_utils import detect_file_type_from_bytes


def test_removed_file_types_are_not_supported() -> None:
    removed_types = (
        FileType.DOC,
        FileType.XLS,
        FileType.PPT,
        FileType.XML,
        FileType.ODT,
        FileType.ODP,
        FileType.ODS,
        FileType.RTF,
        FileType.SVG,
        FileType.HEIC,
        FileType.HEIF,
    )

    assert all(file_type.is_support is False for file_type in removed_types)
    assert FileType.DOCX.is_support is True
    assert FileType.PNG.is_support is True


def test_html_with_inline_svg_is_detected_as_html() -> None:
    data = (
        b"<!doctype html><html><body>"
        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
        b"</body></html>"
    )

    assert detect_file_type_from_bytes(data) is FileType.HTML


def test_svg_document_is_detected_as_svg() -> None:
    data = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"

    assert detect_file_type_from_bytes(data) is FileType.SVG
