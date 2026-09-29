from __future__ import annotations

from enum import Enum


class FileCategory(str, Enum):
    """文件粗分类。"""

    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"


class FileType(str, Enum):
    """具体文件格式。"""

    PDF = "pdf"
    DOC = "doc"
    DOCX = "docx"
    ODT = "odt"
    RTF = "rtf"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"
    XML = "xml"
    CSV = "csv"
    XLS = "xls"
    XLSX = "xlsx"
    ODS = "ods"
    PPT = "ppt"
    PPTX = "pptx"
    ODP = "odp"

    JPG = "jpg"
    PNG = "png"
    GIF = "gif"
    BMP = "bmp"
    WEBP = "webp"
    SVG = "svg"
    HEIC = "heic"
    HEIF = "heif"
    TIFF = "tiff"
    ICO = "ico"

    MP4 = "mp4"
    AVI = "avi"
    MOV = "mov"
    MKV = "mkv"
    FLV = "flv"
    WMV = "wmv"
    WEBM = "webm"
    M4V = "m4v"
    MPEG = "mpeg"
    MPG = "mpg"
    THREE_GP = "3gp"
    TS = "ts"
    MTS = "mts"
    M2TS = "m2ts"

    @property
    def media_type(self) -> str:
        return FILE_TYPE_MEDIA_TYPES[self]

    @property
    def category(self) -> FileCategory:
        """返回文件的粗分类。"""
        return FILE_TYPE_CATEGORIES[self]

    @property
    def is_document(self) -> bool:
        return self.category is FileCategory.DOCUMENT

    @property
    def is_image(self) -> bool:
        return self.category is FileCategory.IMAGE

    @property
    def is_video(self) -> bool:
        return self.category is FileCategory.VIDEO

    @property
    def is_support(self) -> bool:
        return self not in UNSUPPORTED_FILE_TYPES


UNSUPPORTED_FILE_TYPES: frozenset[FileType] = frozenset(
    {
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
    }
)


FILE_TYPE_MEDIA_TYPES: dict[FileType, str] = {
    # Documents
    FileType.PDF: "application/pdf",
    FileType.DOC: "application/msword",
    FileType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileType.ODT: "application/vnd.oasis.opendocument.text",
    FileType.RTF: "application/rtf",
    FileType.TXT: "text/plain",
    FileType.MARKDOWN: "text/markdown",
    FileType.HTML: "text/html",
    FileType.XML: "application/xml",
    FileType.CSV: "text/csv",
    FileType.XLS: "application/vnd.ms-excel",
    FileType.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    FileType.ODS: "application/vnd.oasis.opendocument.spreadsheet",
    FileType.PPT: "application/vnd.ms-powerpoint",
    FileType.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    FileType.ODP: "application/vnd.oasis.opendocument.presentation",

    # Images
    FileType.JPG: "image/jpeg",
    FileType.PNG: "image/png",
    FileType.GIF: "image/gif",
    FileType.BMP: "image/bmp",
    FileType.WEBP: "image/webp",
    FileType.SVG: "image/svg+xml",
    FileType.HEIC: "image/heic",
    FileType.HEIF: "image/heif",
    FileType.TIFF: "image/tiff",
    FileType.ICO: "image/x-icon",

    # Videos
    FileType.MP4: "video/mp4",
    FileType.AVI: "video/x-msvideo",
    FileType.MOV: "video/quicktime",
    FileType.MKV: "video/x-matroska",
    FileType.FLV: "video/x-flv",
    FileType.WMV: "video/x-ms-wmv",
    FileType.WEBM: "video/webm",
    FileType.M4V: "video/x-m4v",
    FileType.MPEG: "video/mpeg",
    FileType.MPG: "video/mpeg",
    FileType.THREE_GP: "video/3gpp",
    FileType.TS: "video/mp2t",
    FileType.MTS: "video/mp2t",
    FileType.M2TS: "video/mp2t",
}

FILE_TYPE_CATEGORIES: dict[FileType, FileCategory] = {
    # Documents
    FileType.PDF: FileCategory.DOCUMENT,
    FileType.DOC: FileCategory.DOCUMENT,
    FileType.DOCX: FileCategory.DOCUMENT,
    FileType.ODT: FileCategory.DOCUMENT,
    FileType.RTF: FileCategory.DOCUMENT,
    FileType.TXT: FileCategory.DOCUMENT,
    FileType.MARKDOWN: FileCategory.DOCUMENT,
    FileType.HTML: FileCategory.DOCUMENT,
    FileType.XML: FileCategory.DOCUMENT,
    FileType.CSV: FileCategory.DOCUMENT,
    FileType.XLS: FileCategory.DOCUMENT,
    FileType.XLSX: FileCategory.DOCUMENT,
    FileType.ODS: FileCategory.DOCUMENT,
    FileType.PPT: FileCategory.DOCUMENT,
    FileType.PPTX: FileCategory.DOCUMENT,
    FileType.ODP: FileCategory.DOCUMENT,

    # Images
    FileType.JPG: FileCategory.IMAGE,
    FileType.PNG: FileCategory.IMAGE,
    FileType.GIF: FileCategory.IMAGE,
    FileType.BMP: FileCategory.IMAGE,
    FileType.WEBP: FileCategory.IMAGE,
    FileType.SVG: FileCategory.IMAGE,
    FileType.HEIC: FileCategory.IMAGE,
    FileType.HEIF: FileCategory.IMAGE,
    FileType.TIFF: FileCategory.IMAGE,
    FileType.ICO: FileCategory.IMAGE,

    # Videos
    FileType.MP4: FileCategory.VIDEO,
    FileType.AVI: FileCategory.VIDEO,
    FileType.MOV: FileCategory.VIDEO,
    FileType.MKV: FileCategory.VIDEO,
    FileType.FLV: FileCategory.VIDEO,
    FileType.WMV: FileCategory.VIDEO,
    FileType.WEBM: FileCategory.VIDEO,
    FileType.M4V: FileCategory.VIDEO,
    FileType.MPEG: FileCategory.VIDEO,
    FileType.MPG: FileCategory.VIDEO,
    FileType.THREE_GP: FileCategory.VIDEO,
    FileType.TS: FileCategory.VIDEO,
    FileType.MTS: FileCategory.VIDEO,
    FileType.M2TS: FileCategory.VIDEO,
}
