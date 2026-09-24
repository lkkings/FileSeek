
from __future__ import annotations


UNKNOWN = "application/octet-stream"


def detect_file_type(data: bytes) -> str:
    """
    根据文件头特征检测文件 MIME Type。

    只检查传入的 bytes，不读取文件、不访问网络、不依赖文件扩展名。

    建议传入：
        4KB ~ 64KB 文件头数据。

    返回：
        MIME Type。
    """

    if not data:
        return UNKNOWN

    # ==========================================================
    # PDF
    # ==========================================================

    if data.startswith(b"%PDF-"):
        return "application/pdf"

    # ==========================================================
    # 图片
    # ==========================================================

    # JPEG / JPG
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    # PNG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    # GIF
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"

    # BMP
    if data.startswith(b"BM"):
        return "image/bmp"

    # TIFF
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"

    # BigTIFF
    if data.startswith((b"II+\x00", b"MM\x00+")):
        return "image/tiff"

    # WebP
    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
    ):
        return "image/webp"

    # JPEG 2000
    if data.startswith(b"\x00\x00\x00\x0cjP  \r\n\x87\n"):
        return "image/jp2"

    # JPEG XL
    if data.startswith(b"\xff\x0a"):
        return "image/jxl"

    if data.startswith(b"\x00\x00\x00\x0cJXL \r\n\x87\n"):
        return "image/jxl"

    # ICO
    if data.startswith(b"\x00\x00\x01\x00"):
        return "image/x-icon"

    # CUR
    if data.startswith(b"\x00\x00\x02\x00"):
        return "image/x-win-bitmap"

    # PSD
    if data.startswith(b"8BPS"):
        return "image/vnd.adobe.photoshop"

    # HEIC / HEIF / AVIF
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]

        if brand in {
            b"heic",
            b"heix",
            b"hevc",
            b"hevx",
        }:
            return "image/heic"

        if brand in {
            b"mif1",
            b"msf1",
        }:
            return "image/heif"

        if brand in {
            b"avif",
            b"avis",
        }:
            return "image/avif"

    # ==========================================================
    # SVG
    # ==========================================================

    # SVG 没有可靠 Magic Number，只能检查文本特征。
    stripped = data.lstrip()

    if (
        stripped.startswith(b"<?xml")
        and b"<svg" in stripped[:4096].lower()
    ):
        return "image/svg+xml"

    if stripped.startswith(b"<svg"):
        return "image/svg+xml"

    # ==========================================================
    # 音频
    # ==========================================================

    # WAV
    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WAVE"
    ):
        return "audio/wav"

    # AIFF
    if (
        len(data) >= 12
        and data[:4] == b"FORM"
        and data[8:12] == b"AIFF"
    ):
        return "audio/aiff"

    # AIFC
    if (
        len(data) >= 12
        and data[:4] == b"FORM"
        and data[8:12] == b"AIFC"
    ):
        return "audio/aiff"

    # FLAC
    if data.startswith(b"fLaC"):
        return "audio/flac"

    # OGG
    if data.startswith(b"OggS"):
        # Opus
        if b"OpusHead" in data[:256]:
            return "audio/ogg"

        # Vorbis
        if b"\x01vorbis" in data[:256]:
            return "audio/ogg"

        return "application/ogg"

    # MIDI
    if data.startswith(b"MThd"):
        return "audio/midi"

    # AMR
    if data.startswith(b"#!AMR"):
        return "audio/amr"

    # MP3 ID3
    if data.startswith(b"ID3"):
        return "audio/mpeg"

    # MP3 Frame
    if len(data) >= 2:
        if (
            data[0] == 0xFF
            and (data[1] & 0xE0) == 0xE0
        ):
            return "audio/mpeg"

    # ==========================================================
    # 视频
    # ==========================================================

    # AVI
    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"AVI "
    ):
        return "video/x-msvideo"

    # WebM / MKV
    if data.startswith(b"\x1A\x45\xDF\xA3"):
        lower = data[:8192].lower()

        if b"webm" in lower:
            return "video/webm"

        if b"matroska" in lower:
            return "video/x-matroska"

        return "video/x-matroska"

    # MP4 / MOV / 3GP / M4V
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]

        # QuickTime
        if brand == b"qt  ":
            return "video/quicktime"

        # MPEG-4
        if brand in {
            b"isom",
            b"iso2",
            b"iso3",
            b"iso4",
            b"iso5",
            b"iso6",
            b"mp41",
            b"mp42",
            b"avc1",
        }:
            return "video/mp4"

        # M4V
        if brand in {
            b"M4V ",
            b"M4VH",
            b"M4VP",
        }:
            return "video/x-m4v"

        # 3GP
        if brand.startswith(b"3gp"):
            return "video/3gpp"

        # 3G2
        if brand.startswith(b"3g2"):
            return "video/3gpp2"

        # HEIF / AVIF 已在图片检测阶段处理
        if brand in {
            b"heic",
            b"heix",
            b"hevc",
            b"hevx",
            b"mif1",
            b"msf1",
            b"avif",
            b"avis",
        }:
            return "application/octet-stream"

        return "video/mp4"

    # MPEG-TS
    if len(data) >= 188:
        if data[0] == 0x47 and data[188] == 0x47:
            return "video/mp2t"

    # MPEG Program Stream
    if data.startswith(b"\x00\x00\x01\xBA"):
        return "video/mpeg"

    # MPEG Video
    if data.startswith(b"\x00\x00\x01\xB3"):
        return "video/mpeg"

    # FLV
    if data.startswith(b"FLV"):
        return "video/x-flv"

    # RealMedia
    if data.startswith(b".RMF"):
        return "application/vnd.rn-realmedia"

    # ==========================================================
    # Microsoft Office / OLE
    # ==========================================================

    # Compound File Binary Format
    if data.startswith(
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    ):
        return _detect_ole(data)

    # ==========================================================
    # ZIP / Office Open XML
    # ==========================================================

    if data.startswith(
        (
            b"PK\x03\x04",
            b"PK\x05\x06",
            b"PK\x07\x08",
        )
    ):
        return _detect_zip(data)

    # ==========================================================
    # OpenDocument
    # ==========================================================

    if data.startswith(b"PK"):
        result = _detect_zip(data)

        if result != "application/zip":
            return result

    # ==========================================================
    # 压缩文件
    # ==========================================================

    # GZIP
    if data.startswith(b"\x1F\x8B"):
        return "application/gzip"

    # BZIP2
    if data.startswith(b"BZh"):
        return "application/x-bzip2"

    # XZ
    if data.startswith(b"\xFD7zXZ\x00"):
        return "application/x-xz"

    # 7-Zip
    if data.startswith(b"7z\xBC\xAF\x27\x1C"):
        return "application/x-7z-compressed"

    # RAR 4
    if data.startswith(b"Rar!\x1A\x07\x00"):
        return "application/vnd.rar"

    # RAR 5
    if data.startswith(b"Rar!\x1A\x07\x01\x00"):
        return "application/vnd.rar"

    # TAR
    if len(data) >= 262 and data[257:262] == b"ustar":
        return "application/x-tar"

    # ==========================================================
    # 文本 / 数据格式
    # ==========================================================

    if _looks_like_json(data):
        return "application/json"

    if _looks_like_xml(data):
        return "application/xml"

    if _looks_like_html(data):
        return "text/html"

    # ==========================================================
    # Unknown
    # ==========================================================

    return UNKNOWN


def _detect_zip(data: bytes) -> str:
    """
    根据 ZIP 内部文件名判断 Office / OpenDocument。

    注意：
    ZIP 中央目录可能位于文件尾部，因此只提供了文件头时，
    不一定能够识别具体 ZIP 子类型。
    """

    # Microsoft Office Open XML
    if b"[Content_Types].xml" in data:
        if b"word/" in data:
            return (
                "application/"
                "vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )

        if b"xl/" in data:
            return (
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )

        if b"ppt/" in data:
            return (
                "application/"
                "vnd.openxmlformats-officedocument."
                "presentationml.presentation"
            )

    # OpenDocument
    if b"mimetypeapplication/vnd.oasis.opendocument.text" in data:
        return "application/vnd.oasis.opendocument.text"

    if b"mimetypeapplication/vnd.oasis.opendocument.spreadsheet" in data:
        return "application/vnd.oasis.opendocument.spreadsheet"

    if b"mimetypeapplication/vnd.oasis.opendocument.presentation" in data:
        return "application/vnd.oasis.opendocument.presentation"

    return "application/zip"


def _detect_ole(data: bytes) -> str:
    """
    判断旧版 Microsoft Office 文件。

    DOC / XLS / PPT 都使用 OLE Compound File。
    """

    if b"WordDocument" in data:
        return "application/msword"

    if b"Workbook" in data or b"Book" in data:
        return "application/vnd.ms-excel"

    if b"PowerPoint Document" in data:
        return "application/vnd.ms-powerpoint"

    return "application/x-ole-storage"


def _looks_like_json(data: bytes) -> bool:
    stripped = data.lstrip()

    if not stripped:
        return False

    return stripped.startswith((b"{", b"["))


def _looks_like_xml(data: bytes) -> bool:
    stripped = data.lstrip()

    if not stripped:
        return False

    lower = stripped[:4096].lower()

    return (
        lower.startswith(b"<?xml")
        or lower.startswith(b"<rss")
        or lower.startswith(b"<feed")
    )


def _looks_like_html(data: bytes) -> bool:
    stripped = data.lstrip().lower()

    return stripped.startswith(
        (
            b"<!doctype html",
            b"<html",
            b"<head",
            b"<body",
        )
    )
