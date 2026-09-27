from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path
from typing import Final

from fileseek.shared.domain.file_types import FileType


DEFAULT_HEADER_SIZE: Final = 64 * 1024


# ============================================================
# Magic Bytes
# ============================================================

PDF_MAGIC: Final = b"%PDF-"

JPEG_MAGIC: Final = b"\xFF\xD8\xFF"

PNG_MAGIC: Final = b"\x89PNG\r\n\x1A\n"

GIF_MAGIC: Final[tuple[bytes, ...]] = (
    b"GIF87a",
    b"GIF89a",
)

BMP_MAGIC: Final = b"BM"

TIFF_MAGIC: Final[tuple[bytes, ...]] = (
    b"II*\x00",
    b"MM\x00*",
)

ICO_MAGIC: Final = b"\x00\x00\x01\x00"

RIFF_MAGIC: Final = b"RIFF"

WEBP_MAGIC: Final = b"WEBP"

AVI_MAGIC: Final = b"AVI "

FLV_MAGIC: Final = b"FLV"

MKV_MAGIC: Final = b"\x1A\x45\xDF\xA3"

RTF_MAGIC: Final = b"{\\rtf"

OLE_MAGIC: Final = bytes.fromhex(
    "D0CF11E0A1B11AE1"
)

ASF_MAGIC: Final = bytes.fromhex(
    "3026B2758E66CF11A6D900AA0062CE6C"
)

ZIP_MAGIC: Final[tuple[bytes, ...]] = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
)


# ISO Base Media File Format
FTYP_MAGIC: Final = b"ftyp"


# ============================================================
# ZIP / OOXML / ODF constants
# ============================================================

OOXML_REQUIRED: Final = "[Content_Types].xml"

OOXML_WORD_PREFIX: Final = "word/"

OOXML_EXCEL_PREFIX: Final = "xl/"

OOXML_POWERPOINT_PREFIX: Final = "ppt/"

ODF_MIMETYPES: Final[dict[str, FileType]] = {
    "application/vnd.oasis.opendocument.text": FileType.ODT,
    "application/vnd.oasis.opendocument.spreadsheet": FileType.ODS,
    "application/vnd.oasis.opendocument.presentation": FileType.ODP,
}


# ============================================================
# ISO media brands
# ============================================================

MP4_BRANDS: Final[frozenset[bytes]] = frozenset(
    {
        b"isom",
        b"iso2",
        b"iso3",
        b"iso4",
        b"iso5",
        b"iso6",
        b"mp41",
        b"mp42",
        b"avc1",
        b"dash",
        b"MSNV",
        b"F4V ",
    }
)

MOV_BRANDS: Final[frozenset[bytes]] = frozenset(
    {
        b"qt  ",
    }
)

M4V_BRANDS: Final[frozenset[bytes]] = frozenset(
    {
        b"M4V ",
    }
)

THREE_GP_BRANDS: Final[frozenset[bytes]] = frozenset(
    {
        b"3gp4",
        b"3gp5",
        b"3gp6",
        b"3gp7",
        b"3g2a",
        b"3g2b",
    }
)

HEIC_BRANDS: Final[frozenset[bytes]] = frozenset(
    {
        b"heic",
        b"heix",
        b"hevc",
        b"hevx",
    }
)

HEIF_BRANDS: Final[frozenset[bytes]] = frozenset(
    {
        b"mif1",
        b"msf1",
    }
)


# ============================================================
# Public API
# ============================================================


def bytes_hash(data: bytes) -> str:
    """计算 bytes 的 SHA-256。"""
    return hashlib.sha256(data).hexdigest()


def detect_file_type(
    source: str | Path | bytes,
    *,
    header_size: int = DEFAULT_HEADER_SIZE,
) -> FileType | None:
    """检测文件具体类型。

    支持：
        - bytes
        - str 文件路径
        - pathlib.Path

    不支持：
        - URL
        - 将 ZIP / 压缩包作为独立 FileType

    注意：
        DOCX / XLSX / PPTX / ODT / ODS / ODP
        虽然内部使用 ZIP 容器，但会检查其内部结构，
        用于识别具体文档格式。

    Args:
        source: 文件路径、Path 或完整 bytes。
        header_size: 普通文件读取的最大头部大小。

    Returns:
        FileType 或 None。
    """
    _validate_header_size(header_size)

    if isinstance(source, bytes):
        return detect_file_type_from_bytes(source)

    if isinstance(source, (str, Path)):
        return detect_file_type_from_file(
            source,
            header_size=header_size,
        )

    return None


def detect_file_type_from_bytes(
    data: bytes,
) -> FileType | None:
    """根据完整文件 bytes 检测类型。"""
    if not data:
        return None

    return _detect_from_bytes(data)


def detect_file_type_from_file(
    path: str | Path,
    *,
    header_size: int = DEFAULT_HEADER_SIZE,
) -> FileType | None:
    """根据本地文件检测类型。

    对普通格式只读取文件头。

    对 DOCX/XLSX/PPTX/ODT/ODS/ODP：
    如果发现 ZIP 容器，则进一步读取 ZIP 中的文件目录，
    用于识别具体格式。

    普通 ZIP 不会返回任何 FileType。
    """
    _validate_header_size(header_size)

    path = Path(path)

    try:
        with path.open("rb") as file:
            header = file.read(header_size)

            if not header:
                return None

            # 先检测无需读取完整文件的格式。
            result = _detect_non_zip_from_bytes(header)

            if result is not None:
                return result

            # 只有 ZIP 容器才进入这里。
            if not _looks_like_zip(header):
                return None

            # 这里不是“检测 ZIP 类型”。
            # 而是检查 ZIP 是否实际上是：
            #
            # DOCX / XLSX / PPTX / ODT / ODS / ODP
            #
            return _detect_zip_document_from_file(file, header)

    except (OSError, ValueError, zipfile.BadZipFile):
        return None


# ============================================================
# Validation
# ============================================================


def _validate_header_size(
    header_size: int,
) -> None:
    if not isinstance(header_size, int):
        raise TypeError("header_size must be int")

    if header_size <= 0:
        raise ValueError(
            "header_size must be greater than 0"
        )


# ============================================================
# Main bytes detector
# ============================================================


def _detect_from_bytes(
    data: bytes,
) -> FileType | None:
    """根据完整 bytes 检测文件类型。"""

    result = _detect_non_zip_from_bytes(data)

    if result is not None:
        return result

    # 只有可能是 ZIP 容器时才进一步检查。
    #
    # 注意：
    # 这里不会返回 ZIP。
    if _looks_like_zip(data):
        return _detect_zip_document_from_bytes(data)

    return None


def _detect_non_zip_from_bytes(
    data: bytes,
) -> FileType | None:
    """检测所有非 ZIP 容器格式。"""

    # --------------------------------------------------------
    # Images
    # --------------------------------------------------------

    result = _detect_image(data)

    if result is not None:
        return result

    # --------------------------------------------------------
    # Documents
    # --------------------------------------------------------

    result = _detect_document(data)

    if result is not None:
        return result

    # --------------------------------------------------------
    # Videos
    # --------------------------------------------------------

    result = _detect_video(data)

    if result is not None:
        return result

    # --------------------------------------------------------
    # Text
    # --------------------------------------------------------

    return _detect_text(data)


# ============================================================
# Image detection
# ============================================================


def _detect_image(
    data: bytes,
) -> FileType | None:

    # JPEG
    if data.startswith(JPEG_MAGIC):
        return FileType.JPG

    # PNG
    if data.startswith(PNG_MAGIC):
        return FileType.PNG

    # GIF
    if data.startswith(GIF_MAGIC):
        return FileType.GIF

    # BMP
    if data.startswith(BMP_MAGIC):
        return FileType.BMP

    # TIFF
    if data.startswith(TIFF_MAGIC):
        return FileType.TIFF

    # ICO
    if data.startswith(ICO_MAGIC):
        return FileType.ICO

    # WEBP
    if _is_webp(data):
        return FileType.WEBP

    # SVG
    if _looks_like_svg(data):
        return FileType.SVG

    # HEIC / HEIF
    iso_type = _detect_iso_media(data)

    if iso_type in (
        FileType.HEIC,
        FileType.HEIF,
    ):
        return iso_type

    return None


def _is_webp(
    data: bytes,
) -> bool:
    return (
        len(data) >= 12
        and data[:4] == RIFF_MAGIC
        and data[8:12] == WEBP_MAGIC
    )


def _looks_like_svg(
    data: bytes,
) -> bool:
    """通过 XML/SVG 文本特征检测 SVG。"""

    sample = data[:16 * 1024]

    try:
        text = sample.decode(
            "utf-8-sig",
            errors="strict",
        )
    except UnicodeDecodeError:
        return False

    text = text.lstrip()

    if not text:
        return False

    lowered = text.lower()

    if lowered.startswith("<svg"):
        return True

    if lowered.startswith("<?xml"):
        return "<svg" in lowered

    if lowered.startswith("<!doctype"):
        return "<svg" in lowered

    return False


# ============================================================
# Document detection
# ============================================================


def _detect_document(
    data: bytes,
) -> FileType | None:

    # PDF
    if data.startswith(PDF_MAGIC):
        return FileType.PDF

    # RTF
    if data.startswith(RTF_MAGIC):
        return FileType.RTF

    # OLE
    if data.startswith(OLE_MAGIC):
        return _detect_ole_document(data)

    return None


# ============================================================
# OLE / DOC / XLS / PPT
# ============================================================


def _detect_ole_document(
    data: bytes,
) -> FileType | None:
    """检测 OLE Compound File 中的 DOC/XLS/PPT。

    DOC / XLS / PPT 都有相同 OLE 文件头：

        D0 CF 11 E0 A1 B1 1A E1

    所以不能只看 magic bytes。

    这里进一步寻找 OLE Directory 中的标准 stream/storage
    名称。

    注意：
    这不是扩展名检测。
    """

    # Word
    if _contains_utf16le_string(
        data,
        "WordDocument",
    ):
        return FileType.DOC

    # Excel
    if _contains_utf16le_string(
        data,
        "Workbook",
    ):
        return FileType.XLS

    if _contains_utf16le_string(
        data,
        "Book",
    ):
        return FileType.XLS

    # PowerPoint
    if _contains_utf16le_string(
        data,
        "PowerPoint Document",
    ):
        return FileType.PPT

    # 有些 PowerPoint 文件会出现：
    # "Current User"
    # "PowerPoint Document"
    #
    # 只凭 Current User 不够，因此不单独使用。

    return None


def _contains_utf16le_string(
    data: bytes,
    value: str,
) -> bool:
    encoded = value.encode("utf-16le")

    return encoded in data


# ============================================================
# ZIP container detection
# ============================================================


def _looks_like_zip(
    data: bytes,
) -> bool:
    """判断是否可能是 ZIP。

    这里只判断 ZIP 容器的 magic，
    不会把 ZIP 当成 FileType 返回。
    """

    return any(
        data.startswith(magic)
        for magic in ZIP_MAGIC
    )


def _detect_zip_document_from_bytes(
    data: bytes,
) -> FileType | None:
    """从 ZIP 容器内部结构识别 OOXML / ODF。

    普通 ZIP 返回 None。
    """

    try:
        with zipfile.ZipFile(
            io.BytesIO(data)
        ) as archive:
            return _detect_zip_document(
                archive
            )
    except (
        zipfile.BadZipFile,
        OSError,
        ValueError,
    ):
        return None


def _detect_zip_document_from_file(
    file,
    header: bytes,
) -> FileType | None:
    """从本地 ZIP 文件内部结构识别 OOXML / ODF。"""

    try:
        # 当前 file 已经读取了 header。
        # seek(0) 后让 ZipFile 自己读取中央目录。
        file.seek(0)

        with zipfile.ZipFile(file) as archive:
            return _detect_zip_document(
                archive
            )

    except (
        zipfile.BadZipFile,
        OSError,
        ValueError,
    ):
        return None


def _detect_zip_document(
    archive: zipfile.ZipFile,
) -> FileType | None:
    """识别已打开的 ZIP 文档容器。"""

    try:
        names = set(archive.namelist())
    except (
        RuntimeError,
        OSError,
        ValueError,
    ):
        return None

    # --------------------------------------------------------
    # ODF
    # --------------------------------------------------------

    odf_type = _detect_odf(archive, names)

    if odf_type is not None:
        return odf_type

    # --------------------------------------------------------
    # OOXML
    # --------------------------------------------------------

    return _detect_ooxml(names)


def _detect_odf(
    archive: zipfile.ZipFile,
    names: set[str],
) -> FileType | None:
    """检测 ODT / ODS / ODP。"""

    if "mimetype" not in names:
        return None

    try:
        mimetype = archive.read(
            "mimetype"
        )
    except (
        KeyError,
        RuntimeError,
        OSError,
        ValueError,
    ):
        return None

    # ODF 要求 mimetype 文件内容准确匹配。
    value = mimetype.decode(
        "ascii",
        errors="ignore",
    ).strip()

    return ODF_MIMETYPES.get(value)


def _detect_ooxml(
    names: set[str],
) -> FileType | None:
    """检测 DOCX / XLSX / PPTX。"""

    if OOXML_REQUIRED not in names:
        return None

    has_word = any(
        name.startswith(OOXML_WORD_PREFIX)
        for name in names
    )

    has_excel = any(
        name.startswith(OOXML_EXCEL_PREFIX)
        for name in names
    )

    has_powerpoint = any(
        name.startswith(
            OOXML_POWERPOINT_PREFIX
        )
        for name in names
    )

    # 必须有明确 OOXML 主目录。
    if has_word:
        return FileType.DOCX

    if has_excel:
        return FileType.XLSX

    if has_powerpoint:
        return FileType.PPTX

    return None


# ============================================================
# Video detection
# ============================================================


def _detect_video(
    data: bytes,
) -> FileType | None:

    # ISO Base Media
    iso_type = _detect_iso_media(data)

    if iso_type in {
        FileType.MP4,
        FileType.MOV,
        FileType.M4V,
        FileType.THREE_GP,
    }:
        return iso_type

    # Matroska / WebM
    if data.startswith(MKV_MAGIC):
        if _looks_like_webm(data):
            return FileType.WEBM

        return FileType.MKV

    # AVI
    if (
        len(data) >= 12
        and data[:4] == RIFF_MAGIC
        and data[8:12] == AVI_MAGIC
    ):
        return FileType.AVI

    # FLV
    if data.startswith(FLV_MAGIC):
        return FileType.FLV

    # MPEG Program Stream
    if _looks_like_mpeg_program_stream(data):
        return FileType.MPEG

    # MPEG Transport Stream
    if _looks_like_mpeg_ts(data):
        return FileType.TS

    # WMV / ASF
    if data.startswith(ASF_MAGIC):
        return FileType.WMV

    return None


# ============================================================
# ISO Base Media
# ============================================================


def _detect_iso_media(
    data: bytes,
) -> FileType | None:
    """检测 MP4/MOV/M4V/3GP/HEIC/HEIF。"""

    if len(data) < 16:
        return None

    # Standard:
    #
    # 4 bytes size
    # 4 bytes "ftyp"
    # 4 bytes major_brand
    # 4 bytes minor_version

    if data[4:8] != FTYP_MAGIC:
        return None

    major_brand = data[8:12]

    # ftyp box size
    box_size = int.from_bytes(
        data[0:4],
        byteorder="big",
        signed=False,
    )

    if box_size < 16:
        return None

    # 只在当前 bytes 范围内读取。
    end = min(
        box_size,
        len(data),
    )

    brands = {
        major_brand,
    }

    # compatible_brands 从 offset 16 开始。
    for offset in range(
        16,
        end - 3,
        4,
    ):
        brands.add(
            data[offset:offset + 4]
        )

    # HEIC
    if brands & HEIC_BRANDS:
        return FileType.HEIC

    # HEIF
    if brands & HEIF_BRANDS:
        return FileType.HEIF

    # MOV / QuickTime
    if brands & MOV_BRANDS:
        return FileType.MOV

    # 3GP / 3G2
    if brands & THREE_GP_BRANDS:
        return FileType.THREE_GP

    # M4V
    if brands & M4V_BRANDS:
        return FileType.M4V

    # MP4
    if brands & MP4_BRANDS:
        return FileType.MP4

    return None


# ============================================================
# Matroska / WebM
# ============================================================


def _looks_like_webm(
    data: bytes,
) -> bool:
    """通过 EBML DocType 判断 WebM。"""

    # EBML:
    #
    # 42 82 = DocType
    # 84    = size 4
    # webm

    return b"\x42\x82\x84webm" in data[:16 * 1024]


# ============================================================
# MPEG
# ============================================================


def _looks_like_mpeg_program_stream(
    data: bytes,
) -> bool:
    """检测 MPEG Program Stream。"""

    # Pack start code
    if data.startswith(
        b"\x00\x00\x01\xBA"
    ):
        return True

    # MPEG video sequence header
    if data.startswith(
        b"\x00\x00\x01\xB3"
    ):
        return True

    return False


# ============================================================
# MPEG TS
# ============================================================


def _looks_like_mpeg_ts(
    data: bytes,
) -> bool:
    """通过连续 TS packet sync byte 检测 MPEG-TS。"""

    # MPEG-TS 常见：
    #
    # 188 bytes
    # 192 bytes
    # 204 bytes
    #
    # 每个 packet 的第一个 byte 是 0x47。

    for packet_size in (
        188,
        192,
        204,
    ):
        if len(data) < packet_size * 3:
            continue

        # 要求至少连续三个 packet 都正确。
        if (
            data[0] == 0x47
            and data[packet_size] == 0x47
            and data[packet_size * 2] == 0x47
        ):
            return True

    return False


# ============================================================
# Text detection
# ============================================================


def _detect_text(
    data: bytes,
) -> FileType | None:
    """检测 HTML/XML/Markdown/CSV/TXT。"""

    if not data:
        return None

    # 文本文件通常不包含 NUL。
    if b"\x00" in data:
        return None

    # UTF-8
    try:
        text = data.decode(
            "utf-8-sig",
            errors="strict",
        )
    except UnicodeDecodeError:
        return None

    if not text.strip():
        return None

    stripped = text.lstrip()

    if not stripped:
        return None

    lowered = stripped.lower()

    # HTML
    if _looks_like_html(lowered):
        return FileType.HTML

    # XML
    if _looks_like_xml(lowered):
        return FileType.XML

    # Markdown
    if _looks_like_markdown(text):
        return FileType.MARKDOWN

    # CSV
    if _looks_like_csv(text):
        return FileType.CSV

    # 剩余可读文本认为是 TXT。
    if _looks_like_plain_text(text):
        return FileType.TXT

    return None


def _looks_like_html(
    text: str,
) -> bool:
    """检测 HTML。"""

    if text.startswith(
        "<!doctype html"
    ):
        return True

    if text.startswith("<html"):
        return True

    sample = text[:8192]

    # 避免仅因为普通文本里出现 <html>
    # 就直接判定 HTML。
    return (
        "<html" in sample
        and "</html" in sample
    )


def _looks_like_xml(
    text: str,
) -> bool:
    """检测 XML。"""

    if text.startswith("<?xml"):
        return True

    # XML declaration 之外，DOCTYPE 也是较强信号。
    if text.startswith("<!doctype"):
        return True

    return False


def _looks_like_markdown(
    text: str,
) -> bool:
    """启发式检测 Markdown。"""

    score = 0

    lines = text.splitlines()

    for line in lines[:100]:
        stripped = line.strip()

        if not stripped:
            continue

        # Heading
        if re.match(
            r"^#{1,6}\s+\S+",
            stripped,
        ):
            score += 2

        # Unordered list
        if re.match(
            r"^[-*+]\s+\S+",
            stripped,
        ):
            score += 1

        # Ordered list
        if re.match(
            r"^\d+\.\s+\S+",
            stripped,
        ):
            score += 1

        # Quote
        if stripped.startswith("> "):
            score += 1

        # Code block
        if stripped.startswith("```"):
            score += 2

        # Markdown link
        if re.search(
            r"\[[^\]]+\]\([^)]+\)",
            stripped,
        ):
            score += 2

        if score >= 2:
            return True

    return False


def _looks_like_csv(
    text: str,
) -> bool:
    """启发式检测 CSV。"""

    lines = [
        line
        for line in text.splitlines()
        if line.strip()
    ]

    if len(lines) < 2:
        return False

    # 只取少量行避免异常大文本扫描。
    lines = lines[:30]

    for delimiter in (
        ",",
        ";",
        "\t",
    ):
        counts = [
            line.count(delimiter)
            for line in lines
        ]

        # 每一行至少一个分隔符。
        if not all(
            count > 0
            for count in counts
        ):
            continue

        # 各行列数一致。
        if len(set(counts)) == 1:
            return True

    return False


def _looks_like_plain_text(
    text: str,
) -> bool:
    """判断是否为普通文本。"""

    # 统计控制字符。
    control_count = 0
    total_count = 0

    for char in text[:16 * 1024]:
        total_count += 1

        code = ord(char)

        if code < 32 and char not in (
            "\r",
            "\n",
            "\t",
            "\f",
        ):
            control_count += 1

    if total_count == 0:
        return False

    # 控制字符比例过高则认为不是普通文本。
    return (
        control_count / total_count
    ) < 0.01
