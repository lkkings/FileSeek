from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fileseek.features.library.application.queries import GetFileQuery
from fileseek.features.library.application.use_cases.get_file_source import (
    GetFileSourceUseCase,
)
from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.features.settings.domain.entities import StorageLocation
from fileseek.features.settings.infrastructure.source_access import (
    LocalSourceFile,
    StorageSourceResolver,
)
from fileseek.shared.domain.file_types import FileCategory, FileType


class FakeFileRepository:
    def __init__(self, file: File) -> None:
        self.file = file

    async def get_by_id(self, file_id: str) -> File | None:
        return self.file if file_id == self.file.id else None

    async def set_access_state(self, file_id: str, access_state: str) -> bool:
        _ = file_id
        self.file.access_state = access_state
        return True


class FakeSourceResolver:
    def __init__(self, source: Path | None) -> None:
        self.source = source

    async def resolve(self, storage_id: str, source_path: str):
        _ = storage_id, source_path
        if self.source is None:
            raise SourceUnavailableError("来源不可用")
        return LocalSourceFile(self.source)


class FakeStorageLocationRepository:
    def __init__(self, location: StorageLocation) -> None:
        self.location = location

    async def get_by_id(
        self,
        location_id: str,
        *,
        include_deleted: bool = False,
    ) -> StorageLocation | None:
        _ = include_deleted
        return self.location if location_id == self.location.id else None


def _file(path: Path, access_state: str) -> File:
    return File(
        id="file-1",
        name="file.txt",
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path=str(path),
        storage_id="local",
        access_state=access_state,
    )


@pytest.mark.asyncio
async def test_get_file_source_keeps_state_when_resolver_fails(
    tmp_path: Path,
) -> None:
    file = _file(tmp_path / "source.txt", "available")
    use_case = GetFileSourceUseCase(
        FakeFileRepository(file),
        FakeSourceResolver(None),
    )

    with pytest.raises(SourceUnavailableError):
        await use_case.execute(GetFileQuery(file_id="file-1"))

    assert file.access_state == "available"


@pytest.mark.asyncio
async def test_get_file_source_does_not_preflight_missing_source(
    tmp_path: Path,
) -> None:
    file = _file(tmp_path / "missing.txt", "available")
    use_case = GetFileSourceUseCase(
        FakeFileRepository(file),
        FakeSourceResolver(tmp_path / "missing.txt"),
    )

    result = await use_case.execute(GetFileQuery(file_id="file-1"))

    assert isinstance(result, LocalSourceFile)
    assert file.access_state == "available"


@pytest.mark.asyncio
async def test_get_file_source_restores_unknown_state(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    file = _file(source, "unknown")
    use_case = GetFileSourceUseCase(
        FakeFileRepository(file),
        FakeSourceResolver(source),
    )

    result = await use_case.execute(GetFileQuery(file_id="file-1"))

    assert result is not None
    assert file.access_state == "unknown"


@pytest.mark.asyncio
async def test_get_file_source_reads_file_uri_when_state_was_unavailable(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("file uri source", encoding="utf-8")
    file = _file(Path(source.as_uri()), "unavailable")
    file.storage_id = "external"
    use_case = GetFileSourceUseCase(
        FakeFileRepository(file),
        StorageSourceResolver(
            FakeStorageLocationRepository(
                StorageLocation(
                    id="external",
                    type="external",
                    name="External",
                    protocol="http",
                    endpoint="",
                )
            )
        ),
    )

    result = await use_case.execute(GetFileQuery(file_id="file-1"))

    with result.open("rb") as source_file:
        assert source_file.read() == b"file uri source"
    assert file.access_state == "unavailable"


@pytest.mark.asyncio
async def test_get_file_source_reads_mounted_nas_relative_path(
    tmp_path: Path,
) -> None:
    nas_root = tmp_path / "nas"
    source = nas_root / "source.txt"
    source.parent.mkdir()
    source.write_text("nas source", encoding="utf-8")
    file = _file(Path("source.txt"), "available")
    file.storage_id = "nas1"
    use_case = GetFileSourceUseCase(
        FakeFileRepository(file),
        StorageSourceResolver(
            FakeStorageLocationRepository(
                StorageLocation(
                    id="nas1",
                    type="nas",
                    name="NAS 1",
                    protocol="mounted",
                    endpoint=str(nas_root),
                    root_path=str(nas_root),
                )
            )
        ),
    )

    result = await use_case.execute(GetFileQuery(file_id="file-1"))

    with result.open("rb") as source_file:
        assert source_file.read() == b"nas source"
    assert file.access_state == "available"
