"""Settings feature 领域实体。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Settings:
    """系统设置实体。"""

    lib_root: str
    nas_enabled: bool = False


@dataclass
class NASConfig:
    """NAS 配置实体。"""

    protocol: str  # smb / nfs / webdav
    host: str
    share_path: str
    username: str
    password: str
