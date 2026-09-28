from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Literal

PreviewSize = Literal["list", "detail"]


class ThumbnailCache:
    """Stores metadata-keyed thumbnails on the local filesystem."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir

    def get(
        self,
        *,
        file_id: str,
        source_size: int,
        source_modified: str | float,
        size: PreviewSize,
    ) -> bytes | None:
        path = self._path_for(
            file_id=file_id,
            source_size=source_size,
            source_modified=source_modified,
            size=size,
        )

        try:
            return path.read_bytes()
        except OSError:
            return None

    def store(
        self,
        *,
        file_id: str,
        source_size: int,
        source_modified: str | float,
        size: PreviewSize,
        data: bytes,
    ) -> None:
        path = self._path_for(
            file_id=file_id,
            source_size=source_size,
            source_modified=source_modified,
            size=size,
        )
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        temporary_fd, temporary_name = tempfile.mkstemp(
            dir=self._cache_dir,
            prefix=f"{path.stem}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(temporary_fd, "wb") as temporary_file:
                temporary_file.write(data)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            Path(temporary_name).replace(path)
        except OSError:
            with contextlib.suppress(OSError):
                Path(temporary_name).unlink()
            raise

    def _path_for(
        self,
        *,
        file_id: str,
        source_size: int,
        source_modified: str | float,
        size: PreviewSize,
    ) -> Path:
        key = json.dumps(
            {
                "file_id": file_id,
                "source_size": source_size,
                "source_modified": source_modified,
                "size": size,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(key).hexdigest()
        return self._cache_dir / f"{digest}.webp"
