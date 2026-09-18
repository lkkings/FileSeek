"""User settings, loaded from and saved to the config file.

Everything here is validated on load: the config file is a system boundary, so a
hand-edited value must fail with a clear message rather than surface later as a
confusing runtime error. Secrets never appear here — the NAS password lives in
the OS keychain and this file only records that a credential exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import yaml

from fileseek.models.tiers import DevicePreference
from fileseek.paths import AppPaths, is_network_path

NasProtocol = Literal["smb", "nfs", "webdav"]

DEFAULT_MAX_CONCURRENT = 3
MAX_ALLOWED_CONCURRENT = 16

DEFAULT_VIDEO_FPS = 1.0
MAX_VIDEO_FPS = 10.0

DEFAULT_THUMBNAIL_SIZE = (320, 180)

DEFAULT_HEALTH_CHECK_SECONDS = 30


class ConfigError(ValueError):
    """A setting is missing, malformed, or out of range."""

    def __init__(self, field_name: str, reason: str) -> None:
        super().__init__(f"invalid setting {field_name!r}: {reason}")
        self.field_name = field_name
        self.reason = reason


def _require_positive_int(value: object, field_name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(field_name, f"expected a whole number, got {value!r}")
    if not 1 <= value <= maximum:
        raise ConfigError(field_name, f"must be between 1 and {maximum}, got {value}")
    return value


def _require_str(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(field_name, f"expected a non-empty string, got {value!r}")
    return value


@dataclass(frozen=True)
class NasSettings:
    """How to reach a library that lives on a NAS.

    The password is deliberately absent: `has_credential` only records that one is
    stored in the OS keychain under this host and username.
    """

    enabled: bool = False
    protocol: NasProtocol = "smb"
    host: str = ""
    share: str = ""
    username: str = ""
    has_credential: bool = False
    auto_discover: bool = True
    health_check_seconds: int = DEFAULT_HEALTH_CHECK_SECONDS

    @property
    def credential_key(self) -> str:
        """Identifies this connection's entry in the OS keychain."""
        return f"{self.protocol}://{self.username}@{self.host}/{self.share}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "protocol": self.protocol,
            "host": self.host,
            "share": self.share,
            "username": self.username,
            "has_credential": self.has_credential,
            "auto_discover": self.auto_discover,
            "health_check_seconds": self.health_check_seconds,
        }

    @classmethod
    def from_dict(cls, raw: object) -> NasSettings:
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise ConfigError("nas", f"expected a mapping, got {type(raw).__name__}")

        protocol = raw.get("protocol", "smb")
        if protocol not in ("smb", "nfs", "webdav"):
            raise ConfigError("nas.protocol", f"must be smb, nfs or webdav, got {protocol!r}")

        enabled = bool(raw.get("enabled", False))
        host = str(raw.get("host", "") or "")
        if enabled and not host:
            raise ConfigError("nas.host", "a host is required when NAS support is enabled")

        seconds = raw.get("health_check_seconds", DEFAULT_HEALTH_CHECK_SECONDS)
        return cls(
            enabled=enabled,
            protocol=protocol,
            host=host,
            share=str(raw.get("share", "") or ""),
            username=str(raw.get("username", "") or ""),
            has_credential=bool(raw.get("has_credential", False)),
            auto_discover=bool(raw.get("auto_discover", True)),
            health_check_seconds=_require_positive_int(
                seconds, "nas.health_check_seconds", maximum=3600
            ),
        )


@dataclass(frozen=True)
class ProcessingSettings:
    max_concurrent: int = DEFAULT_MAX_CONCURRENT
    video_fps: float = DEFAULT_VIDEO_FPS
    thumbnail_size: tuple[int, int] = DEFAULT_THUMBNAIL_SIZE
    device_preference: DevicePreference = "auto"

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_concurrent": self.max_concurrent,
            "video_fps": self.video_fps,
            "thumbnail_size": list(self.thumbnail_size),
            "device_preference": self.device_preference,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ProcessingSettings:
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise ConfigError("processing", f"expected a mapping, got {type(raw).__name__}")

        preference = raw.get("device_preference", "auto")
        if preference not in ("auto", "gpu", "cpu"):
            raise ConfigError(
                "processing.device_preference",
                f"must be auto, gpu or cpu, got {preference!r}",
            )

        fps = raw.get("video_fps", DEFAULT_VIDEO_FPS)
        if isinstance(fps, bool) or not isinstance(fps, int | float):
            raise ConfigError("processing.video_fps", f"expected a number, got {fps!r}")
        if not 0 < fps <= MAX_VIDEO_FPS:
            raise ConfigError(
                "processing.video_fps", f"must be greater than 0 and at most {MAX_VIDEO_FPS}"
            )

        size = raw.get("thumbnail_size", list(DEFAULT_THUMBNAIL_SIZE))
        if not isinstance(size, list | tuple) or len(size) != 2:
            raise ConfigError("processing.thumbnail_size", "expected a [width, height] pair")
        width = _require_positive_int(size[0], "processing.thumbnail_size[0]", maximum=4096)
        height = _require_positive_int(size[1], "processing.thumbnail_size[1]", maximum=4096)

        return cls(
            max_concurrent=_require_positive_int(
                raw.get("max_concurrent", DEFAULT_MAX_CONCURRENT),
                "processing.max_concurrent",
                maximum=MAX_ALLOWED_CONCURRENT,
            ),
            video_fps=float(fps),
            thumbnail_size=(width, height),
            device_preference=preference,
        )


@dataclass(frozen=True)
class Settings:
    """The whole user-facing configuration."""

    library_root: Path | None = None
    model_dir: Path | None = None
    processing: ProcessingSettings = field(default_factory=ProcessingSettings)
    nas: NasSettings = field(default_factory=NasSettings)

    @property
    def is_configured(self) -> bool:
        """False on first run, when the library root has not been chosen yet."""
        return self.library_root is not None

    def apply_to(self, paths: AppPaths) -> AppPaths:
        return paths.with_model_dir(self.model_dir)

    def with_library_root(self, root: Path | str) -> Settings:
        return replace(self, library_root=Path(root))

    def to_dict(self) -> dict[str, Any]:
        return {
            "library": {
                "root": None if self.library_root is None else str(self.library_root),
            },
            "models": {
                "path": None if self.model_dir is None else str(self.model_dir),
            },
            "processing": self.processing.to_dict(),
            "nas": self.nas.to_dict(),
        }

    @classmethod
    def from_dict(cls, raw: object) -> Settings:
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise ConfigError("<root>", f"expected a mapping, got {type(raw).__name__}")

        library = raw.get("library") or {}
        if not isinstance(library, dict):
            raise ConfigError("library", f"expected a mapping, got {type(library).__name__}")
        root_raw = library.get("root")
        library_root = None
        if root_raw is not None:
            library_root = Path(_require_str(root_raw, "library.root"))

        models = raw.get("models") or {}
        if not isinstance(models, dict):
            raise ConfigError("models", f"expected a mapping, got {type(models).__name__}")
        model_raw = models.get("path")
        model_dir = None
        if model_raw is not None:
            model_dir = Path(_require_str(model_raw, "models.path"))
            # Weights are read on every model load; a share would make that crawl.
            if is_network_path(model_dir):
                raise ConfigError("models.path", "must be a local path, not a network share")

        return cls(
            library_root=library_root,
            model_dir=model_dir,
            processing=ProcessingSettings.from_dict(raw.get("processing")),
            nas=NasSettings.from_dict(raw.get("nas")),
        )


def load_settings(path: Path) -> Settings:
    """Read settings from path, returning defaults when the file does not exist."""
    if not path.is_file():
        return Settings()
    text = path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError("<file>", f"could not parse {path}: {error}") from error
    return Settings.from_dict(parsed)


def save_settings(settings: Settings, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(settings.to_dict(), sort_keys=True, allow_unicode=True)
    # Write then rename, so an interrupted save cannot truncate a good config.
    staging = path.with_name(path.name + ".writing")
    staging.write_text(payload, encoding="utf-8")
    staging.replace(path)
    return path
