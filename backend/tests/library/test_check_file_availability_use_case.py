from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fileseek.features.library.application.queries import (
    CheckFileAvailabilityQuery,
)
from fileseek.features.library.application.use_cases.check_file_availability import (
    CheckFileAvailabilityUseCase,
)
from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.features.settings.infrastructure.source_access import LocalSourceFile
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
    def __init__(self, available: bool) -> None:
        self.available = available

    async def resolve(self, storage_id: str, source_path: str):
        _ = storage_id
        if not self.available:
            raise SourceUnavailableError("来源不可用")
        return LocalSourceFile(Path(source_path))


def _file(path: Path) -> File:
    return File(
        id="file-1",
        name="file.txt",
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path=str(path),
        storage_id="local",
        access_state="unavailable",
    )


@pytest.mark.asyncio
async def test_availability_check_restores_available_source(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("available", encoding="utf-8")
    file = _file(source)
    use_case = CheckFileAvailabilityUseCase(
        FakeFileRepository(file),
        FakeSourceResolver(available=True),
    )

    result = await use_case.execute(CheckFileAvailabilityQuery(file_id="file-1"))

    assert result.access_state == "available"
    assert file.access_state == "available"


@pytest.mark.asyncio
async def test_availability_check_marks_missing_file_unavailable(
    tmp_path: Path,
) -> None:
    file = _file(tmp_path / "source.txt")
    file.access_state = "available"
    use_case = CheckFileAvailabilityUseCase(
        FakeFileRepository(file),
        FakeSourceResolver(available=True),
    )

    result = await use_case.execute(CheckFileAvailabilityQuery(file_id="file-1"))

    assert result.access_state == "unavailable"
    assert file.access_state == "unavailable"


@pytest.mark.asyncio
async def test_availability_check_keeps_state_when_resolver_fails(
    tmp_path: Path,
) -> None:
    file = _file(tmp_path / "source.txt")
    file.access_state = "available"
    use_case = CheckFileAvailabilityUseCase(
        FakeFileRepository(file),
        FakeSourceResolver(available=False),
    )

    result = await use_case.execute(CheckFileAvailabilityQuery(file_id="file-1"))

    assert result.access_state == "available"
    assert file.access_state == "available"
