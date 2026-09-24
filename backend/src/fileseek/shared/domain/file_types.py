from __future__ import annotations

from enum import Enum


class FileType(str, Enum):
    """文件类型。"""

    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"

    @classmethod
    def from_extension(cls, extension: str) -> FileType | None:
        """根据文件扩展名推断文件类型。

        注意：
            此方法仅根据扩展名进行推断，不代表文件的真实内容类型。

        Args:
            extension: 文件扩展名，可以包含或不包含前导点。

        Returns:
            对应的文件类型，无法识别时返回 None。
        """
        extension = extension.lower().lstrip(".")

        if extension in DOCUMENT_EXTENSIONS:
            return cls.DOCUMENT

        if extension in IMAGE_EXTENSIONS:
            return cls.IMAGE

        if extension in VIDEO_EXTENSIONS:
            return cls.VIDEO

        return None

    @classmethod
    def from_mime(cls, mime_type: str) -> FileType | None:
        """根据 MIME Type 推断文件类型。

        Args:
            mime_type: MIME 类型，例如 application/pdf。

        Returns:
            对应的文件类型，无法识别时返回 None。
        """
        mime_type = mime_type.lower().strip()

        if mime_type in DOCUMENT_MIME_TYPES:
            return cls.DOCUMENT

        if mime_type in IMAGE_MIME_TYPES:
            return cls.IMAGE

        if mime_type in VIDEO_MIME_TYPES:
            return cls.VIDEO

        return None


DOCUMENT_EXTENSIONS = frozenset(
    {
        "pdf",
        "doc",
        "docx",
        "odt",
        "rtf",
        "txt",
        "md",
        "markdown",
        "html",
        "htm",
        "xml",
        "csv",
        "xls",
        "xlsx",
        "ods",
        "ppt",
        "pptx",
        "odp",
    }
)

IMAGE_EXTENSIONS = frozenset(
    {
        "jpg",
        "jpeg",
        "png",
        "gif",
        "bmp",
        "webp",
        "svg",
        "heic",
        "heif",
        "tif",
        "tiff",
        "ico",
    }
)

VIDEO_EXTENSIONS = frozenset(
    {
        "mp4",
        "avi",
        "mov",
        "mkv",
        "flv",
        "wmv",
        "webm",
        "m4v",
        "mpeg",
        "mpg",
        "3gp",
        "ts",
        "mts",
        "m2ts",
    }
)


DOCUMENT_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.oasis.opendocument.text",
        "application/rtf",
        "text/plain",
        "text/markdown",
        "text/html",
        "application/xhtml+xml",
        "text/csv",
        "application/xml",
        "text/xml",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.oasis.opendocument.presentation",
    }
)

IMAGE_MIME_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/bmp",
        "image/webp",
        "image/svg+xml",
        "image/heic",
        "image/heif",
        "image/tiff",
        "image/x-icon",
    }
)

VIDEO_MIME_TYPES = frozenset(
    {
        "video/mp4",
        "video/mpeg",
        "video/quicktime",
        "video/x-msvideo",
        "video/x-matroska",
        "video/x-flv",
        "video/x-ms-wmv",
        "video/webm",
        "video/x-m4v",
        "video/3gpp",
        "video/mp2t",
    }
)