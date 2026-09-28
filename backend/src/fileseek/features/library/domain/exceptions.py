"""Library feature 领域异常。"""

from __future__ import annotations

from fileseek.shared.domain.exceptions import ApplicationError, NotFoundError


class FolderNotFoundError(NotFoundError):
    """文件夹未找到。"""


class FileNotFoundError(NotFoundError):  # noqa: A001
    """文件未找到。"""


class RecycleItemNotFoundError(NotFoundError):
    """回收站条目未找到。"""


class ThumbnailUnavailableError(ApplicationError):
    """缩略图生成失败。"""


class SourceUnavailableError(ApplicationError):
    """索引来源不可访问。"""


class FolderNotEmptyError(ApplicationError):
    """文件夹非空，无法删除。"""
