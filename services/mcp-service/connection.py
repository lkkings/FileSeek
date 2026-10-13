"""管理 FileSeek Backend 的连接信息（动态 token）。"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional


class ConnectionError(Exception):
    """连接错误。"""
    pass


class ConnectionManager:
    """管理 FileSeek Backend 的连接信息（动态 token）。"""

    def __init__(self, connection_path: Optional[Path] = None):
        self.path = connection_path or self._get_default_path()
        self._cached_connection: Optional[dict] = None
        self._last_mtime: Optional[float] = None
        self._last_check_time: float = 0
        self._check_interval: float = 1.0  # 最多每秒检查一次

    @staticmethod
    def _get_default_path() -> Path:
        """根据平台返回默认的 connection.json 路径。"""
        # 优先从环境变量读取
        env_path = os.environ.get("FILESEEK_CONNECTION_FILE")
        if env_path:
            return Path(env_path)

        # 根据平台返回默认路径
        if sys.platform == "darwin":
            return Path.home() / "Library/Application Support/FileSeek/connection.json"
        elif sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            if not appdata:
                raise ConnectionError("Windows 环境变量 APPDATA 未设置")
            return Path(appdata) / "FileSeek/connection.json"
        else:  # Linux
            return Path.home() / ".config/FileSeek/connection.json"

    def get_connection(self) -> dict:
        """获取最新的连接信息（port, token）。

        带缓存和 mtime 检测，避免频繁读文件。

        Returns:
            连接信息字典，包含 port 和 token

        Raises:
            ConnectionError: Backend 未运行或连接文件损坏
        """
        now = time.time()

        # 限制检查频率（避免每个请求都 stat）
        if now - self._last_check_time < self._check_interval:
            if self._cached_connection:
                return self._cached_connection

        self._last_check_time = now

        try:
            # 检查文件是否变化
            current_mtime = self.path.stat().st_mtime

            if self._cached_connection and current_mtime == self._last_mtime:
                return self._cached_connection

            # 文件变化了，重新读取
            data = json.loads(self.path.read_text(encoding="utf-8"))

            # 验证必需字段
            if "port" not in data or "token" not in data:
                raise ValueError("连接文件缺少必需字段 (port, token)")

            self._cached_connection = data
            self._last_mtime = current_mtime

            return data

        except FileNotFoundError:
            raise ConnectionError(
                f"FileSeek Backend 未运行。\n"
                f"连接文件不存在: {self.path}\n"
                f"请确保 FileSeek Desktop 应用正在运行。"
            )
        except (json.JSONDecodeError, ValueError) as e:
            raise ConnectionError(f"连接文件损坏: {e}")

    def get_api_url(self) -> str:
        """获取 Backend API 的完整 URL。"""
        conn = self.get_connection()
        return f"http://127.0.0.1:{conn['port']}/api/v1"

    def get_token(self) -> str:
        """获取当前有效的认证 token。"""
        conn = self.get_connection()
        return conn["token"]
