"""Per-platform locations for FileSeek's own state.

The index and metadata database must stay on local disk (see library-storage),
so these resolve independently of wherever the user's library lives.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path, PurePath
from typing import Literal

APP_NAME = "FileSeek"

Platform = Literal["win32", "darwin", "linux"]


class UnsupportedPlatformError(RuntimeError):
    pass


def normalize_platform(raw: str) -> Platform:
    if raw == "win32":
        return "win32"
    if raw == "darwin":
        return "darwin"
    if raw.startswith("linux"):
        return "linux"
    raise UnsupportedPlatformError(f"unsupported platform: {raw!r}")


def _first_env_path(env: Mapping[str, str], *names: str) -> Path | None:
    for name in names:
        raw = env.get(name)
        if raw:
            return Path(raw)
    return None


@dataclass(frozen=True)
class AppPaths:
    """Resolved base directories, plus the concrete files built on top of them."""

    config_dir: Path
    data_dir: Path
    cache_dir: Path
    # Model weights run to gigabytes, so they can be moved off a small system
    # drive without relocating the rest of the app's state.
    model_dir_override: Path | None = None

    @property
    def database_path(self) -> Path:
        return self.data_dir / "metadata.db"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.yaml"

    @property
    def connection_file(self) -> Path:
        """Holds the loopback port and auth token for extensions and the UI."""
        return self.config_dir / "connection.json"

    @property
    def thumbnail_cache_dir(self) -> Path:
        return self.cache_dir / "thumbnails"

    @property
    def model_dir(self) -> Path:
        if self.model_dir_override is not None:
            return self.model_dir_override
        return self.data_dir / "models"

    def with_model_dir(self, model_dir: Path | str | None) -> AppPaths:
        """Return a copy whose weights live elsewhere; None restores the default."""
        return replace(
            self,
            model_dir_override=None if model_dir is None else Path(model_dir),
        )

    def all_dirs(self) -> tuple[Path, ...]:
        return (self.config_dir, self.data_dir, self.cache_dir)

    def create_dirs(self) -> None:
        for directory in (*self.all_dirs(), self.index_dir, self.thumbnail_cache_dir):
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def resolve(
        cls,
        platform: str | None = None,
        env: Mapping[str, str] | None = None,
        home: Path | None = None,
    ) -> AppPaths:
        if env is None:
            import os

            env = os.environ
        target = normalize_platform(platform if platform is not None else sys.platform)
        base_home = home if home is not None else Path.home()

        if target == "win32":
            roaming = _first_env_path(env, "APPDATA") or base_home / "AppData" / "Roaming"
            local = _first_env_path(env, "LOCALAPPDATA") or base_home / "AppData" / "Local"
            return cls(
                config_dir=roaming / APP_NAME,
                data_dir=local / APP_NAME,
                cache_dir=local / APP_NAME / "Cache",
            )

        if target == "darwin":
            support = base_home / "Library" / "Application Support" / APP_NAME
            return cls(
                config_dir=support,
                data_dir=support,
                cache_dir=base_home / "Library" / "Caches" / APP_NAME,
            )

        config_home = _first_env_path(env, "XDG_CONFIG_HOME") or base_home / ".config"
        data_home = _first_env_path(env, "XDG_DATA_HOME") or base_home / ".local" / "share"
        cache_home = _first_env_path(env, "XDG_CACHE_HOME") or base_home / ".cache"
        slug = APP_NAME.lower()
        return cls(
            config_dir=config_home / slug,
            data_dir=data_home / slug,
            cache_dir=cache_home / slug,
        )


def is_network_path(path: PurePath | str) -> bool:
    """True for locations SQLite must not live on: UNC shares and mapped drives.

    SQLite's locking is unreliable over network filesystems, so the database and
    the vector index are rejected outright rather than silently corrupted later.
    """
    text = str(path)
    if not text:
        return False
    normalized = text.replace("\\", "/")
    if normalized.startswith("//"):
        return True
    return normalized.startswith(("smb:", "nfs:", "afp:", "webdav:", "dav:", "ftp:", "sftp:"))
