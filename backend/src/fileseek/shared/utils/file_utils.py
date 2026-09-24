from __future__ import annotations

from enum import Enum
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import hashlib

from fileseek.shared.domain.file_types import FileType


DEFAULT_HEADER_SIZE = 16 * 1024
DEFAULT_TIMEOUT = 10




def bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_file_type(
    source: str | Path | bytes,
    *,
    header_size: int = DEFAULT_HEADER_SIZE,
    timeout: float = DEFAULT_TIMEOUT,
) -> FileType | None:
    """检测文件类型。

    支持：
    - 本地文件路径
    - HTTP / HTTPS URL
    - bytes

    检测基于文件特征，不依赖文件扩展名。

    URL 场景只读取文件头，不下载完整文件。

    Args:
        source: 文件路径、URL 或文件字节。
        header_size: 最多读取的文件头大小。
        timeout: URL 请求超时时间。

    Returns:
        检测到的文件类型，无法识别时返回 None。
    """
    data = _read_source(
        source,
        header_size=header_size,
        timeout=timeout,
    )

    if not data:
        return None

    return _detect_from_bytes(data)


def detect_file_type_from_bytes(data: bytes) -> FileType | None:
    """直接根据 bytes 检测文件类型。"""
    if not data:
        return None

    return _detect_from_bytes(data)


def detect_file_type_from_file(
    path: str | Path,
    *,
    header_size: int = DEFAULT_HEADER_SIZE,
) -> FileType | None:
    """根据本地文件检测类型。"""
    data = _read_file(
        Path(path),
        header_size=header_size,
    )

    if not data:
        return None

    return _detect_from_bytes(data)


def detect_file_type_from_url(
    url: str,
    *,
    header_size: int = DEFAULT_HEADER_SIZE,
    timeout: float = DEFAULT_TIMEOUT,
) -> FileType | None:
    """根据 URL 检测文件类型。

    只读取文件头，不下载完整文件。
    """
    data = _read_url(
        url,
        header_size=header_size,
        timeout=timeout,
    )

    if not data:
        return None

    return _detect_from_bytes(data)


def _read_source(
    source: str | Path | bytes,
    *,
    header_size: int,
    timeout: float,
) -> bytes | None:
    """读取数据源的文件头。"""

    if isinstance(source, bytes):
        return source[:header_size]

    if isinstance(source, Path):
        return _read_file(
            source,
            header_size=header_size,
        )

    if isinstance(source, str):
        if _is_url(source):
            return _read_url(
                source,
                header_size=header_size,
                timeout=timeout,
            )

        return _read_file(
            Path(source),
            header_size=header_size,
        )

    return None


def _read_file(
    path: Path,
    *,
    header_size: int,
) -> bytes | None:
    """读取本地文件头。"""

    try:
        with path.open("rb") as file:
            return file.read(header_size)
    except OSError:
        return None


def _read_url(
    url: str,
    *,
    header_size: int,
    timeout: float,
) -> bytes | None:
    """读取 URL 文件头。

    优先通过 HTTP Range 请求获取文件头。

    即使服务器不支持 Range，也只读取 header_size
    字节，然后立即关闭连接。
    """

    request = Request(
        url,
        headers={
            "Range": f"bytes=0-{header_size - 1}",
            "Accept-Encoding": "identity",
            "User-Agent": "FileSeek/1.0",
        },
    )

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            return response.read(header_size)

    except (
        HTTPError,
        URLError,
        OSError,
    ):
        return None


def _detect_from_bytes(data: bytes) -> FileType | None:
    """根据文件特征检测类型。"""

    # ============================================================
    # Image
    # ============================================================

    # JPEG
    if data.startswith(b"\xFF\xD8\xFF"):
        return FileType.IMAGE

    # PNG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return FileType.IMAGE

    # GIF
    if data.startswith(
        (
            b"GIF87a",
            b"GIF89a",
        )
    ):
        return FileType.IMAGE

    # BMP
    if data.startswith(b"BM"):
        return FileType.IMAGE

    # TIFF
    if data.startswith(
        (
            b"II*\x00",
            b"MM\x00*",
        )
    ):
        return FileType.IMAGE

    # WEBP
    if (
        data.startswith(b"RIFF")
        and len(data) >= 12
        and data[8:12] == b"WEBP"
    ):
        return FileType.IMAGE

    # ICO
    if (
        len(data) >= 4
        and data[:4] == b"\x00\x00\x01\x00"
    ):
        return FileType.IMAGE

    # ============================================================
    # Document
    # ============================================================

    # PDF
    if data.startswith(b"%PDF-"):
        return FileType.DOCUMENT

    # Microsoft Office 97-2003
    #
    # DOC / XLS / PPT 等 OLE Compound File
    if data.startswith(
        b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
    ):
        return FileType.DOCUMENT

    # ZIP-based Office:
    #
    # DOCX
    # XLSX
    # PPTX
    # ODT
    # ODS
    # ODP
    #
    # 这里只能判断它属于文档类 ZIP 容器。
    if data.startswith(b"PK\x03\x04"):
        return FileType.DOCUMENT

    # ============================================================
    # Video
    # ============================================================

    # Matroska / MKV / WebM
    if data.startswith(b"\x1A\x45\xDF\xA3"):
        return FileType.VIDEO

    # MP4 / MOV / 3GP 等 ISO Base Media
    if _is_iso_base_media(data):
        return FileType.VIDEO

    # AVI
    if (
        data.startswith(b"RIFF")
        and len(data) >= 12
        and data[8:12] == b"AVI "
    ):
        return FileType.VIDEO

    # MPEG
    if data.startswith(b"\x00\x00\x01\xBA"):
        return FileType.VIDEO

    if data.startswith(b"\x00\x00\x01\xB3"):
        return FileType.VIDEO

    # FLV
    if data.startswith(b"FLV"):
        return FileType.VIDEO

    # ============================================================
    # Text-based document
    # ============================================================

    if _looks_like_svg(data):
        return FileType.IMAGE

    if _looks_like_text_document(data):
        return FileType.DOCUMENT

    return None


def _is_iso_base_media(data: bytes) -> bool:
    """判断 MP4 / MOV / 3GP 等 ISO Base Media 文件。"""

    if len(data) < 12:
        return False

    # ISO Base Media:
    #
    # 4 bytes: box size
    # 4 bytes: box type
    # ...
    #
    # 第一个 box 通常是 ftyp。
    if data[4:8] != b"ftyp":
        return False

    brand_data = data[8:64]

    known_brands = (
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
        b"mmp4",
        b"3gp",
        b"3g2",
        b"qt",
    )

    return any(
        brand in brand_data
        for brand in known_brands
    )


def _looks_like_svg(data: bytes) -> bool:
    """判断是否可能是 SVG。"""

    try:
        text = data.decode(
            "utf-8-sig",
            errors="ignore",
        ).lstrip()

    except UnicodeDecodeError:
        return False

    if not text:
        return False

    # XML declaration
    if text.startswith("<?xml"):
        return "<svg" in text[:4096].lower()

    return text.lower().startswith("<svg")


def _looks_like_text_document(data: bytes) -> bool:
    """判断是否可能是普通文本文件。"""

    if not data:
        return False

    # 存在大量 NUL，通常说明是二进制文件。
    if b"\x00" in data:
        return False

    try:
        text = data.decode(
            "utf-8-sig",
            errors="strict",
        )
    except UnicodeDecodeError:
        return False

    if not text.strip():
        return False

    # 普通文本只能作为 DOCUMENT。
    return True


def _is_url(source: str) -> bool:
    """判断是否为 HTTP / HTTPS URL。"""

    parsed = urlparse(source)

    return parsed.scheme.lower() in {
        "http",
        "https",
    }



