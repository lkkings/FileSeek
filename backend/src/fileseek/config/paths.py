"""路径管理。

`LibraryPaths` 管理文件库内部的目录结构，`AppPaths` 管理应用级配置目录
（连接文件、配置文件、日志）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


class AppPaths:
    """应用级目录：配置文件、连接文件、日志。

    这里的路径是和桌面端的硬约定：Rust 侧的 `sidecar::connection_file_path`
    按同样的规则算出同一个文件并轮询它。改这里必须同步改那边，否则桌面端
    起不来——它拿不到端口和 token。
    """

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    @classmethod
    def resolve(cls) -> AppPaths:
        """按平台惯例定位配置目录。"""
        home = Path.home()
        # 经一个变量再比较：直接写 sys.platform == "win32" 会让类型检查器按当前
        # 平台把其余分支判成不可达，而这段代码就是要在三个平台上都成立。
        platform: str = sys.platform

        if platform == "win32":
            appdata = os.environ.get("APPDATA")
            roaming = Path(appdata) if appdata else home / "AppData" / "Roaming"
            return cls(roaming / "FileSeek")

        if platform == "darwin":
            return cls(home / "Library" / "Application Support" / "FileSeek")

        xdg = os.environ.get("XDG_CONFIG_HOME")
        config_home = Path(xdg) if xdg else home / ".config"
        return cls(config_home / "fileseek")

    @property
    def connection_file(self) -> Path:
        """`{port, token}` 的发布位置，客户端据此连接。"""
        return self.config_dir / "connection.json"

    @property
    def log_file(self) -> Path:
        """服务日志。"""
        return self.config_dir / "fileseek.log"

    def ensure_directories(self) -> None:
        """确保配置目录存在。"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
