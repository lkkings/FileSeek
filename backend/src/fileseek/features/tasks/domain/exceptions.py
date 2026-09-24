"""Tasks feature 领域异常。"""

from __future__ import annotations

from fileseek.shared.application.exceptions import ApplicationError, NotFoundError


class TaskNotFoundError(NotFoundError):
    """任务未找到。"""


class InvalidTransitionError(ApplicationError):
    """非法状态转换。"""


class DocumentParseError(RuntimeError):
    """文档损坏或无法解析。"""


class UnsupportedFormatError(ValueError):
    """不支持的文档格式。"""


class ModelLoadError(RuntimeError):
    """模型加载失败。"""


class InferenceError(RuntimeError):
    """模型推理失败。"""

class ImageProcessError(RuntimeError):
    """图片文件损坏或格式不支持。"""


class VideoProcessError(RuntimeError):
    """视频文件损坏或格式不支持。"""