from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import gettempdir

import pytest

from fileseek.features.library.infrastructure.repositories import FileRepositoryImpl
from fileseek.infrastructure.database.models import FileModel
from fileseek.shared.domain.file_types import FileCategory, FileType

test_path = str(Path(gettempdir()) / "file.txt")


@pytest.mark.asyncio
async def test_file_repository_updates_access_state(settings) -> None:
    repository = FileRepositoryImpl()
    await FileModel.create(
        id="file-1",
        name="file.txt",
        file_type=FileType.TXT.value,
        category=FileCategory.DOCUMENT.value,
        size=1,
        modified=datetime.now(UTC),
        path=test_path,
        storage_id="local",
        access_state="available",
    )

    assert await repository.set_access_state("file-1", "unavailable") is True
    model = await FileModel.get(id="file-1")

    assert model.access_state == "unavailable"
    assert model.last_checked_at is not None


@pytest.mark.asyncio
async def test_file_repository_marks_storage_unavailable(settings) -> None:
    repository = FileRepositoryImpl()
    await FileModel.create(
        id="file-1",
        name="file.txt",
        file_type=FileType.TXT.value,
        category=FileCategory.DOCUMENT.value,
        size=1,
        modified=datetime.now(UTC),
        path=test_path,
        storage_id="nas1",
        access_state="available",
    )

    affected = await repository.mark_unavailable_by_storage("nas1")
    model = await FileModel.get(id="file-1")

    assert affected == 1
    assert model.access_state == "unavailable"
    assert model.last_checked_at is not None
