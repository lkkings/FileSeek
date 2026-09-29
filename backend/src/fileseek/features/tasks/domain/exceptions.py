"""Tasks feature 领域异常。"""

from __future__ import annotations

from fileseek.shared.domain.exceptions import ApplicationError, NotFoundError


class TaskNotFoundError(NotFoundError):
    """任务未找到。"""


class InvalidTransitionError(ApplicationError):
    """非法状态转换。"""


class TaskCancelledError(ApplicationError):
    """任务被用户终止。"""


class DocumentParseError(RuntimeError):
    """文档损坏或无法解析。"""


class UnsupportedFormatError(ValueError):
    """不支持的文档格式。"""


class VideoProcessError(RuntimeError):
    """视频文件损坏或格式不支持。"""
