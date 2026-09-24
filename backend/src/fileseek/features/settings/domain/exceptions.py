"""Settings feature domain 异常。"""

from __future__ import annotations

from fileseek.shared.application.exceptions import ApplicationError


class InvalidPathError(ApplicationError):
    """路径不可写或无效。"""


class NASConnectionError(ApplicationError):
    """NAS 连接失败。"""
