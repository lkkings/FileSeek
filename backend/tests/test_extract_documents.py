import io
from pathlib import Path

import pytest
from PIL import Image

from fileseek.extract.documents import (
    MAX_OCR_PAGES,
    MIN_MEANINGFUL_CHARS,
    UnreadableDocumentError,
    extract_text,
    rasterize_pages,
)

from doc_fixtures import write_docx, write_pdf

CHINESE_PARAGRAPH = "这是一篇关于深度学习的论文综述，涵盖了卷积网络与注意力机制。"


def test_plain_text_is_extracted(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("a survey of transformer architectures", encoding="utf-8")

    extracted = extract_text(target)

    assert "transformer" in extracted.text
    assert extracted.source == "embedded"
    assert extracted.has_text is True


def test_markdown_is_extracted(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    target.write_text("# Deep learning\n\nA survey of recent work.", encoding="utf-8")

    extracted = extract_text(target)

    assert "Deep learning" in extracted.text


def test_chinese_text_survives_extraction(tmp_path: Path) -> None:
    target = tmp_path / "paper.txt"
    target.write_text(CHINESE_PARAGRAPH, encoding="utf-8")

    assert extract_text(target).text == CHINESE_PARAGRAPH


def test_gb18030_text_is_decoded(tmp_path: Path) -> None:
    target = tmp_path / "legacy.txt"
    target.write_bytes(CHINESE_PARAGRAPH.encode("gb18030"))

    assert "深度学习" in extract_text(target).text


def test_utf8_bom_is_stripped(tmp_path: Path) -> None:
    target = tmp_path / "bom.txt"
    target.write_bytes(b"\xef\xbb\xbfhello world from a bom file")

    assert extract_text(target).text.startswith("hello")


def test_whitespace_is_normalized(tmp_path: Path) -> None:
    target = tmp_path / "messy.txt"
    target.write_text("line one   \n\n\n\n   line two\n\n\n", encoding="utf-8")

    assert extract_text(target).text == "line one\n\nline two"


def test_windows_line_endings_are_normalized(tmp_path: Path) -> None:
    target = tmp_path / "crlf.txt"
    target.write_bytes(b"first line\r\nsecond line\r\n")

    assert extract_text(target).text == "first line\nsecond line"


def test_pdf_text_and_page_count_are_extracted(tmp_path: Path) -> None:
    target = write_pdf(
        tmp_path / "paper.pdf",
        ["Deep learning survey paper", "second page about transformers"],
    )

    extracted = extract_text(target)

    assert extracted.page_count == 2
    assert "Deep learning survey" in extracted.text
    assert "transformers" in extracted.text


def test_pdf_pages_are_joined_in_order(tmp_path: Path) -> None:
    target = write_pdf(tmp_path / "paper.pdf", ["first page here", "second page here"])

    text = extract_text(target).text

    assert text.index("first page") < text.index("second page")


def test_scanned_pdf_reports_that_ocr_is_needed(tmp_path: Path) -> None:
    """A page with no text layer must be flagged, not treated as an empty document."""
    target = write_pdf(tmp_path / "scan.pdf", [""])

    extracted = extract_text(target)

    assert extracted.has_text is False
    assert extracted.needs_ocr is True
    assert extracted.page_count == 1


def test_pdf_with_real_text_does_not_need_ocr(tmp_path: Path) -> None:
    target = write_pdf(tmp_path / "paper.pdf", ["a genuinely long line of readable text"])

    assert extract_text(target).needs_ocr is False


def test_trivial_text_layer_still_needs_ocr(tmp_path: Path) -> None:
    target = write_pdf(tmp_path / "scan.pdf", ["x"])

    assert extract_text(target).needs_ocr is True


def test_corrupt_pdf_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "broken.pdf"
    target.write_bytes(b"%PDF-1.4\nthis is not really a pdf")

    with pytest.raises(UnreadableDocumentError, match="could not read document") as excinfo:
        extract_text(target)

    assert excinfo.value.path == target


def test_empty_pdf_file_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "empty.pdf"
    target.write_bytes(b"")

    with pytest.raises(UnreadableDocumentError):
        extract_text(target)


def test_docx_paragraphs_are_extracted(tmp_path: Path) -> None:
    target = write_docx(tmp_path / "paper.docx", ["first paragraph", "second paragraph"])

    extracted = extract_text(target)

    assert "first paragraph" in extracted.text
    assert "second paragraph" in extracted.text


def test_docx_chinese_text_survives(tmp_path: Path) -> None:
    target = write_docx(tmp_path / "paper.docx", [CHINESE_PARAGRAPH])

    assert "深度学习" in extract_text(target).text


def test_docx_table_cells_are_extracted(tmp_path: Path) -> None:
    target = write_docx(
        tmp_path / "paper.docx",
        ["intro paragraph"],
        table_rows=[["accuracy", "0.94"], ["latency", "12ms"]],
    )

    text = extract_text(target).text

    assert "accuracy" in text
    assert "12ms" in text


def test_docx_has_no_page_count(tmp_path: Path) -> None:
    """DOCX has no fixed pagination, so the field stays unknown rather than guessed."""
    target = write_docx(tmp_path / "paper.docx", ["some text here to be long enough"])

    assert extract_text(target).page_count is None


def test_corrupt_docx_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "broken.docx"
    target.write_bytes(b"PK\x03\x04 but not really a docx")

    with pytest.raises(UnreadableDocumentError):
        extract_text(target)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(UnreadableDocumentError, match="does not exist"):
        extract_text(tmp_path / "absent.pdf")


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "sheet.xlsx"
    target.write_bytes(b"whatever")

    with pytest.raises(UnreadableDocumentError, match="unsupported document type"):
        extract_text(target)


def test_extension_matching_ignores_case(tmp_path: Path) -> None:
    target = tmp_path / "NOTES.TXT"
    target.write_text("readable content here", encoding="utf-8")

    assert extract_text(target).has_text is True


def test_empty_text_file_has_no_usable_text(tmp_path: Path) -> None:
    target = tmp_path / "empty.txt"
    target.write_text("", encoding="utf-8")

    extracted = extract_text(target)

    assert extracted.text == ""
    assert extracted.has_text is False


def test_short_text_is_not_considered_meaningful(tmp_path: Path) -> None:
    target = tmp_path / "tiny.txt"
    target.write_text("x" * (MIN_MEANINGFUL_CHARS - 1), encoding="utf-8")

    assert extract_text(target).has_text is False


def test_undecodable_bytes_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "binary.txt"
    target.write_bytes(b"\xff\xfe\x00\x01")

    def always_fail(self: Path, encoding: str | None = None) -> str:
        raise UnicodeDecodeError(encoding or "utf-8", b"", 0, 1, "forced")

    monkeypatch.setattr(Path, "read_text", always_fail)

    with pytest.raises(UnreadableDocumentError, match="could not decode"):
        extract_text(target)


def test_scanned_pdf_pages_can_be_rasterized(tmp_path: Path) -> None:
    """A scan carries no text layer, so its pages must be readable as pixels."""
    target = write_pdf(tmp_path / "scan.pdf", ["", ""])

    rendered = rasterize_pages(target)

    assert len(rendered) == 2
    for payload in rendered:
        with Image.open(io.BytesIO(payload)) as image:
            assert image.mode == "RGB"
            assert min(image.size) > 0


def test_rasterization_is_capped_for_long_scans(tmp_path: Path) -> None:
    target = write_pdf(tmp_path / "long.pdf", [""] * 20)

    assert len(rasterize_pages(target, max_pages=3)) == 3


def test_rasterization_of_a_short_pdf_returns_every_page(tmp_path: Path) -> None:
    target = write_pdf(tmp_path / "short.pdf", [""])

    assert len(rasterize_pages(target, max_pages=MAX_OCR_PAGES)) == 1


def test_rasterization_scale_changes_the_output_size(tmp_path: Path) -> None:
    target = write_pdf(tmp_path / "scan.pdf", [""])

    small = rasterize_pages(target, scale=1.0)[0]
    large = rasterize_pages(target, scale=2.0)[0]

    with Image.open(io.BytesIO(small)) as first, Image.open(io.BytesIO(large)) as second:
        assert second.size[0] > first.size[0]


def test_rasterizing_a_corrupt_pdf_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "broken.pdf"
    target.write_bytes(b"%PDF-1.4 not really")

    with pytest.raises(UnreadableDocumentError):
        rasterize_pages(target)


def test_non_positive_page_cap_is_rejected(tmp_path: Path) -> None:
    target = write_pdf(tmp_path / "scan.pdf", [""])

    with pytest.raises(ValueError, match="max_pages must be positive"):
        rasterize_pages(target, max_pages=0)


def test_unreadable_text_file_reports_the_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "locked.txt"
    target.write_text("content", encoding="utf-8")
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, encoding=None: (_ for _ in ()).throw(OSError("device not ready")),
    )

    with pytest.raises(UnreadableDocumentError, match="device not ready"):
        extract_text(target)
