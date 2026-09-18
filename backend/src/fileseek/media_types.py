"""The single source of truth for which files FileSeek accepts.

The native shell extensions decide whether to show the context-menu entry from
this same list, so it is exported as JSON rather than duplicated per platform.
"""

from __future__ import annotations

import json
from pathlib import Path

from fileseek.db.records import MediaType

DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx", ".txt", ".md"})

IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"})

VIDEO_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".mov", ".mkv", ".avi", ".webm"})

EXTENSIONS_BY_TYPE: dict[MediaType, frozenset[str]] = {
    "document": DOCUMENT_EXTENSIONS,
    "image": IMAGE_EXTENSIONS,
    "video": VIDEO_EXTENSIONS,
}

_TYPE_BY_EXTENSION: dict[str, MediaType] = {
    extension: media_type
    for media_type, extensions in EXTENSIONS_BY_TYPE.items()
    for extension in extensions
}

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_TYPE_BY_EXTENSION)


def media_type_for(path: Path | str) -> MediaType | None:
    """The media type for path, or None when the extension is not supported."""
    suffix = Path(path).suffix.lower()
    return _TYPE_BY_EXTENSION.get(suffix)


def is_supported(path: Path | str) -> bool:
    return media_type_for(path) is not None


def filter_supported(paths: list[Path] | list[str]) -> list[Path]:
    """Keep only the supported paths, so a mixed selection ingests silently."""
    return [Path(path) for path in paths if is_supported(path)]


def manifest() -> str:
    """The extension list as JSON, for the native extensions to consume."""
    return json.dumps(
        {media_type: sorted(ext) for media_type, ext in EXTENSIONS_BY_TYPE.items()},
        indent=2,
        sort_keys=True,
    )
