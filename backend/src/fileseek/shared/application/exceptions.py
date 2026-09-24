"""跨 Feature 共享的业务异常类型。"""

from __future__ import annotations


class ApplicationError(Exception):
    """应用层业务异常基类。"""


class NotFoundError(ApplicationError):
    """资源未找到异常。"""


class ValidationError(ApplicationError):
    """输入验证失败异常。"""

class FileNotSupportError(ApplicationError):
    """文件不支持"""


class FileAlreadyExistsError(ApplicationError):
    """目标文件已存在。"""