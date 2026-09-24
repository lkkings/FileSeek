"""配置模块，统一管理所有系统配置。"""

from fileseek.config.paths import AppPaths, LibraryPaths
from fileseek.config.settings import Settings, get_settings

__all__ = [
    "AppPaths",
    "Settings",
    "get_settings",
    "LibraryPaths",
]
