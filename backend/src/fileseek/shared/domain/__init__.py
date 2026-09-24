"""Shared domain 层模块。"""

from fileseek.shared.domain.identifiers import generate_id
from fileseek.shared.domain.file_types import FileType

__all__ = [
    "generate_id",
    "FileType"
]
