"""Library feature 领域异常。"""

from __future__ import annotations

from fileseek.shared.application.exceptions import ApplicationError, NotFoundError


class FolderNotFoundError(NotFoundError):
    """文件夹未找到。"""


class FileNotFoundError(NotFoundError):  # noqa: A001
    """文件未找到。"""


class RecycleItemNotFoundError(NotFoundError):
    """回收站条目未找到。"""


class FolderNotEmptyError(ApplicationError):
    """文件夹非空，无法删除。"""
