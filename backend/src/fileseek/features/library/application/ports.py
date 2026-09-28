from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import IO, Protocol

from fileseek.features.library.application.dto import ImportTaskSnapshotDTO


@dataclass(frozen=True)
class SourceMetadata:
    size: int
    modified: datetime


class SourceFile(Protocol):
    def exists(self) -> bool: ...

    def is_file(self) -> bool: ...

    def stat(self) -> Mapping[str, object]: ...

    def open(self, mode: str = "rb") -> IO[bytes]: ...

    def __str__(self) -> str: ...


class FileSourcePort(Protocol):
    async def resolve(
        self,
        storage_id: str,
        source_path: str,
    ) -> SourceFile: ...

    async def read_metadata(
        self,
        storage_id: str,
        source_path: str,
    ) -> SourceMetadata: ...


class ImportTaskProgressPort(Protocol):
    async def get_snapshots(
        self,
        task_ids: tuple[str, ...],
    ) -> dict[str, ImportTaskSnapshotDTO]: ...
