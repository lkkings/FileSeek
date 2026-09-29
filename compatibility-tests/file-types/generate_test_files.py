from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

import av
from docx import Document
from odf.draw import Frame, Page, TextBox
from odf.opendocument import OpenDocumentPresentation, OpenDocumentSpreadsheet, OpenDocumentText
from odf.style import MasterPage, PageLayout, PageLayoutProperties, Style, TextProperties
from odf.table import Table, TableCell, TableRow
from odf.text import H, P
from openpyxl import Workbook
from PIL import Image
from pptx import Presentation
from pypdf import PdfWriter


COMPATIBILITY_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = COMPATIBILITY_DIRECTORY.parents[1]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "test"
CONTRACT_PATH = COMPATIBILITY_DIRECTORY / "file-types.json"


DOWNLOADS = {
    "sample.doc": {
        "url": "https://raw.githubusercontent.com/apache/poi/trunk/test-data/document/simple.doc",
        "license": "Apache-2.0",
        "source": "Apache POI test data",
    },
    "sample.xls": {
        "url": "https://raw.githubusercontent.com/apache/poi/trunk/test-data/spreadsheet/SimpleWithColours.xls",
        "license": "Apache-2.0",
        "source": "Apache POI test data",
    },
    "sample.ppt": {
        "url": "https://raw.githubusercontent.com/apache/poi/trunk/test-data/slideshow/basic_test_ppt_file.ppt",
        "license": "Apache-2.0",
        "source": "Apache POI test data",
    },
    "sample.heic": {
        "url": "https://raw.githubusercontent.com/strukturag/libheif/master/examples/example.heic",
        "license": "MIT",
        "source": "libheif example images",
    },
}

VIDEO_RECIPES = {
    "sample.mp4": ("mp4", "libx264", "Generated with PyAV and H.264."),
    "sample.avi": ("avi", "mpeg4", "Generated with PyAV and MPEG-4 Part 2."),
    "sample.mov": ("mov", "libx264", "Generated with PyAV and H.264."),
    "sample.mkv": ("matroska", "libx264", "Generated with PyAV and H.264."),
    "sample.flv": ("flv", "flv", "Generated with PyAV and Sorenson Spark FLV."),
    "sample.wmv": ("asf", "wmv2", "Generated with PyAV and Windows Media Video 2."),
    "sample.webm": ("webm", "vp8", "Generated with PyAV and VP8."),
    "sample.m4v": ("mp4", "libx264", "Generated with PyAV and H.264."),
    "sample.mpeg": ("mpeg", "mpeg2video", "Generated with PyAV and MPEG-2 video."),
    "sample.mpg": ("mpeg", "mpeg2video", "Generated with PyAV and MPEG-2 video."),
    "sample.3gp": ("3gp", "h263", "Generated with PyAV and H.263."),
    "sample.ts": ("mpegts", "libx264", "Generated with PyAV and H.264."),
    "sample.mts": ("mpegts", "libx264", "Generated with PyAV and H.264."),
    "sample.m2ts": (
        "mpegts",
        "libx264",
        "Generated with PyAV H.264 and normalized to standard MPEG-TS packets.",
    ),
}

VIDEO_FRAME_COUNTS = {
    "sample.mp4": 10,
    "sample.avi": 10,
    "sample.mov": 10,
    "sample.mkv": 10,
    "sample.flv": 10,
    "sample.wmv": 10,
    "sample.webm": 10,
    "sample.m4v": 10,
    "sample.mpeg": 10,
    "sample.mpg": 11,
    "sample.3gp": 10,
    "sample.ts": 10,
    "sample.mts": 12,
    "sample.m2ts": 13,
}

GENERATED_SOURCES = {
    "sample.pdf": ("generated", "Generated with pypdf as a one-page PDF.", "https://github.com/py-pdf/pypdf", "BSD-3-Clause"),
    "sample.docx": ("generated", "Generated with python-docx.", "https://github.com/python-openxml/python-docx", "MIT"),
    "sample.odt": ("generated", "Generated with odfpy.", "https://github.com/eea/odfpy", "Apache-2.0 OR GPL-2.0-or-later"),
    "sample.rtf": ("generated", "Generated as a standards-compliant RTF document.", None, "Project test fixture"),
    "sample.txt": ("generated", "Generated as UTF-8 plain text.", None, "Project test fixture"),
    "sample.md": ("generated", "Generated as UTF-8 Markdown.", None, "Project test fixture"),
    "sample.html": ("generated", "Generated as UTF-8 HTML.", None, "Project test fixture"),
    "sample.xml": ("generated", "Generated as UTF-8 XML.", None, "Project test fixture"),
    "sample.csv": ("generated", "Generated as UTF-8 CSV.", None, "Project test fixture"),
    "sample.xlsx": ("generated", "Generated with openpyxl.", "https://github.com/python-openxml/openpyxl", "MIT"),
    "sample.ods": ("generated", "Generated with odfpy.", "https://github.com/eea/odfpy", "Apache-2.0 OR GPL-2.0-or-later"),
    "sample.pptx": ("generated", "Generated with python-pptx.", "https://github.com/python-openxml/python-pptx", "MIT"),
    "sample.odp": ("generated", "Generated with odfpy.", "https://github.com/eea/odfpy", "Apache-2.0 OR GPL-2.0-or-later"),
    "sample.jpg": ("generated", "Generated with Pillow.", "https://github.com/python-pillow/Pillow", "HPND"),
    "sample.png": ("generated", "Generated with Pillow.", "https://github.com/python-pillow/Pillow", "HPND"),
    "sample.gif": ("generated", "Generated with Pillow.", "https://github.com/python-pillow/Pillow", "HPND"),
    "sample.bmp": ("generated", "Generated with Pillow.", "https://github.com/python-pillow/Pillow", "HPND"),
    "sample.webp": ("generated", "Generated with Pillow.", "https://github.com/python-pillow/Pillow", "HPND"),
    "sample.svg": ("generated", "Generated as a standards-compliant SVG image.", None, "Project test fixture"),
    "sample.tiff": ("generated", "Generated with Pillow.", "https://github.com/python-pillow/Pillow", "HPND"),
    "sample.ico": ("generated", "Generated with Pillow.", "https://github.com/python-pillow/Pillow", "HPND"),
}


def _write_bytes(path: Path, content: bytes) -> None:
    path.write_bytes(content)


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _create_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=320, height=240)
    with path.open("wb") as output:
        writer.write(output)


def _create_docx(path: Path) -> None:
    document = Document()
    document.add_heading("FileSeek compatibility sample", level=1)
    document.add_paragraph("This DOCX document is generated with python-docx.")
    document.core_properties.created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    document.core_properties.modified = datetime(2026, 1, 1, tzinfo=timezone.utc)
    document.save(path)


def _create_rtf(path: Path) -> None:
    _write_text(
        path,
        r"{\rtf1\ansi\deff0{\fonttbl{\f0 Helvetica;}}"
        r"\fs24 FileSeek compatibility sample\par"
        r"This RTF document can be opened by standard RTF readers.\par}",
    )


def _create_xlsx(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Compatibility"
    sheet["A1"] = "FileSeek"
    sheet["B1"] = "XLSX compatibility"
    sheet["A2"] = "Generated"
    sheet["B2"] = "openpyxl"
    workbook.save(path)


def _create_pptx(path: Path) -> None:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[0])
    slide.shapes.title.text = "FileSeek compatibility sample"
    slide.placeholders[1].text = "Generated with python-pptx"
    presentation.save(path)


def _create_odt(path: Path) -> None:
    document = OpenDocumentText()
    style = Style(name="Body", family="text")
    style.addElement(TextProperties(fontsize="12pt"))
    document.styles.addElement(style)
    document.text.addElement(H(outlinelevel="1", text="FileSeek compatibility sample"))
    document.text.addElement(P(stylename=style, text="Generated with odfpy."))
    document.save(str(path))


def _create_ods(path: Path) -> None:
    document = OpenDocumentSpreadsheet()
    table = Table(name="Compatibility")
    row = TableRow()
    for cell_value in ("FileSeek", "ODS compatibility"):
        cell = TableCell()
        cell.addElement(P(text=cell_value))
        row.addElement(cell)
    table.addElement(row)
    document.spreadsheet.addElement(table)
    document.save(str(path))


def _create_odp(path: Path) -> None:
    document = OpenDocumentPresentation()
    page_layout = PageLayout(name="PageLayout1")
    page_layout.addElement(PageLayoutProperties(pagewidth="10in", pageheight="7.5in"))
    document.automaticstyles.addElement(page_layout)
    document.masterstyles.addElement(
        MasterPage(name="Default", pagelayoutname=page_layout)
    )
    page = Page(masterpagename="Default")
    frame = Frame(width="8in", height="1.5in", x="1in", y="3in")
    text_box = TextBox()
    text_box.addElement(H(outlinelevel="1", text="FileSeek compatibility sample"))
    text_box.addElement(P(text="Generated with odfpy."))
    frame.addElement(text_box)
    page.addElement(frame)
    document.presentation.addElement(page)
    document.save(str(path))


def _image() -> Image.Image:
    image = Image.new("RGB", (64, 64), "#1f6feb")
    for x_position in range(8, 56, 16):
        for y_position in range(8, 56, 16):
            image.paste(Image.new("RGB", (8, 8), "#f0f6fc"), (x_position, y_position))
    return image


def _create_images() -> None:
    image = _image()
    image.save(OUTPUT_DIRECTORY / "sample.jpg", "JPEG", quality=90)
    image.save(OUTPUT_DIRECTORY / "sample.png", "PNG")
    image.save(OUTPUT_DIRECTORY / "sample.gif", "GIF")
    image.save(OUTPUT_DIRECTORY / "sample.bmp", "BMP")
    image.save(OUTPUT_DIRECTORY / "sample.webp", "WEBP", lossless=True)
    image.save(OUTPUT_DIRECTORY / "sample.tiff", "TIFF")
    image.save(OUTPUT_DIRECTORY / "sample.ico", "ICO", sizes=[(16, 16), (32, 32), (64, 64)])


def _create_video(path: Path, container: str, codec: str, frame_count: int) -> None:
    frame_rate = Fraction(5, 1)
    dimensions = (128, 96) if codec == "h263" else (64, 64)
    frames = [
        _image().resize(dimensions).rotate(index * 3)
        for index in range(frame_count)
    ]

    with av.open(path, mode="w", format=container) as output:
        stream = output.add_stream(codec, rate=frame_rate)
        stream.width = dimensions[0]
        stream.height = dimensions[1]
        stream.pix_fmt = "yuv420p"
        if codec == "libx264":
            stream.codec_context.options = {"preset": "ultrafast", "tune": "stillimage"}

        for frame_index, frame in enumerate(frames):
            video_frame = av.VideoFrame.from_image(frame)
            video_frame.pts = frame_index
            for packet in stream.encode(video_frame):
                output.mux(packet)

        for packet in stream.encode():
            output.mux(packet)


def _download_file(path: Path, url: str) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        content = response.read()
    path.write_bytes(content)


def _write_heif_fixture(path: Path, heic_path: Path) -> None:
    content = bytearray(heic_path.read_bytes())
    if content[4:8] != b"ftyp":
        raise RuntimeError("HEIC fixture does not start with an ftyp box")
    content[8:12] = b"mif1"
    for offset in range(16, 28, 4):
        brand = bytes(content[offset : offset + 4])
        if brand in {b"heic", b"heix", b"hevc", b"hevx"}:
            content[offset : offset + 4] = b"mif1"
    path.write_bytes(content)


def _write_m4v_fixture(path: Path, mp4_path: Path) -> None:
    content = bytearray(mp4_path.read_bytes())
    if content[4:8] != b"ftyp":
        raise RuntimeError("MP4 fixture does not start with an ftyp box")
    content[8:12] = b"M4V "
    if content[16:20] != b"M4V ":
        content[16:20] = b"M4V "
    path.write_bytes(content)


def _write_m2ts_fixture(path: Path) -> None:
    content = path.read_bytes()
    if content[4] != 0x47 or len(content) % 192:
        raise RuntimeError("M2TS fixture is not in BDAV packet layout")
    packets = [
        content[offset + 4 : offset + 192]
        for offset in range(0, len(content), 192)
    ]
    path.write_bytes(b"".join(packets))


def _generate_all_files(contract: list[dict[str, Any]]) -> None:
    _create_pdf(OUTPUT_DIRECTORY / "sample.pdf")
    _create_docx(OUTPUT_DIRECTORY / "sample.docx")
    _create_rtf(OUTPUT_DIRECTORY / "sample.rtf")
    _create_xlsx(OUTPUT_DIRECTORY / "sample.xlsx")
    _create_pptx(OUTPUT_DIRECTORY / "sample.pptx")
    _create_odt(OUTPUT_DIRECTORY / "sample.odt")
    _create_ods(OUTPUT_DIRECTORY / "sample.ods")
    _create_odp(OUTPUT_DIRECTORY / "sample.odp")

    text_files = {
        "sample.txt": "FileSeek plain text compatibility sample.\n",
        "sample.md": "# FileSeek Markdown sample\n\nThis file is valid UTF-8 Markdown.\n",
        "sample.html": "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"><title>FileSeek sample</title></head><body><h1>HTML compatibility sample</h1></body></html>\n",
        "sample.xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<root><name>FileSeek XML compatibility sample</name></root>\n",
        "sample.csv": "name,purpose\nFileSeek,CSV compatibility sample\n",
        "sample.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"64\" height=\"64\" viewBox=\"0 0 64 64\"><rect width=\"64\" height=\"64\" fill=\"#1f6feb\"/><rect x=\"8\" y=\"8\" width=\"8\" height=\"8\" fill=\"#f0f6fc\"/></svg>\n",
    }
    for file_name, content in text_files.items():
        _write_text(OUTPUT_DIRECTORY / file_name, content)

    _create_images()

    for file_name, (container, codec, _) in VIDEO_RECIPES.items():
        _create_video(
            OUTPUT_DIRECTORY / file_name,
            container,
            codec,
        VIDEO_FRAME_COUNTS[file_name],
        )

    _write_m4v_fixture(OUTPUT_DIRECTORY / "sample.m4v", OUTPUT_DIRECTORY / "sample.mp4")
    _write_m2ts_fixture(OUTPUT_DIRECTORY / "sample.m2ts")

    for file_name, metadata in DOWNLOADS.items():
        _download_file(OUTPUT_DIRECTORY / file_name, metadata["url"])

    _write_heif_fixture(OUTPUT_DIRECTORY / "sample.heif", OUTPUT_DIRECTORY / "sample.heic")

    for entry in contract:
        if not (OUTPUT_DIRECTORY / entry["fileName"]).is_file():
            raise RuntimeError(f"Missing generated file: {entry['fileName']}")


def _source_record(file_name: str) -> dict[str, str | None]:
    if file_name in DOWNLOADS:
        metadata = DOWNLOADS[file_name]
        return {
            "origin": "downloaded",
            "source": metadata["source"],
            "sourceUrl": metadata["url"],
            "license": metadata["license"],
        }
    if file_name in VIDEO_RECIPES:
        return {
            "origin": "generated",
            "source": VIDEO_RECIPES[file_name][2],
            "sourceUrl": "https://github.com/PyAV-Org/PyAV",
            "license": "BSD-2-Clause",
        }
    if file_name == "sample.heif":
        return {
            "origin": "derived",
            "source": "libheif example image with the ISO HEIF mif1 brand",
            "sourceUrl": "https://raw.githubusercontent.com/strukturag/libheif/master/examples/example.heic",
            "license": "MIT",
        }
    if file_name in GENERATED_SOURCES:
        origin, source, source_url, license_name = GENERATED_SOURCES[file_name]
        return {
            "origin": origin,
            "source": source,
            "sourceUrl": source_url,
            "license": license_name,
        }
    raise RuntimeError(f"No source metadata for {file_name}")


def _build_manifest(contract: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for entry in contract:
        path = OUTPUT_DIRECTORY / entry["fileName"]
        content = path.read_bytes()
        manifest.append(
            {
                "fileName": entry["fileName"],
                "fileType": entry["fileType"],
                "detectedFileType": entry["detectedFileType"],
                "category": entry["category"],
                "mediaType": entry["mediaType"],
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                **_source_record(entry["fileName"]),
            }
        )
    return manifest


def _write_readme() -> None:
    _write_text(
        OUTPUT_DIRECTORY / "README.md",
        """# FileSeek file-type compatibility fixtures

This directory contains one valid, openable sample for every backend-supported file type.

- `manifest.json` records each file's size, SHA-256 checksum, origin, source URL, and license.
- Legacy Office and HEIF samples are downloaded from Apache POI and libheif.
- Most files are generated with Pillow, PyAV, python-docx, openpyxl, python-pptx, odfpy, or pypdf.
- `mpg`, `mts`, and `m2ts` are independently encoded MPEG-2 or MPEG-TS samples with distinct checksums.

Regenerate all fixtures with:

```sh
cd backend
uv run --with openpyxl --with python-pptx --with odfpy --with python-docx --with pypdf python ../compatibility-tests/file-types/generate_test_files.py
```
""",
    )


def generate_test_files() -> None:
    with CONTRACT_PATH.open(encoding="utf-8") as contract_file:
        contract = json.load(contract_file)

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for path in OUTPUT_DIRECTORY.iterdir():
        if path.is_file():
            path.unlink()

    _generate_all_files(contract)
    manifest = _build_manifest(contract)
    _write_bytes(
        OUTPUT_DIRECTORY / "manifest.json",
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    _write_readme()
    print(f"Created {len(manifest)} fixtures in {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    generate_test_files()
