from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchFileMetadata:
    """Read model returned by the search application."""

    path: str
    size: int | None
    modified: str | None
    accessible: bool
