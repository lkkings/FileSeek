from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import gettempdir

import pytest

from fileseek.features.library.domain.entities import File
from fileseek.features.library.infrastructure.repositories import FileRepositoryImpl
from fileseek.infrastructure.database.models import FileModel, FolderModel, TagModel
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
async def test_file_repository_save_creates_tags_with_ids(settings) -> None:
    repository = FileRepositoryImpl()
    file = File(
        id="file-with-tags",
        name="report.pdf",
        file_type=FileType.PDF,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path=test_path,
        storage_id="local",
        access_state="available",
        tags=["document", "report"],
    )

    await repository.save(file)

    tags = await TagModel.filter(name__in=["document", "report"])
    file_model = await FileModel.get(id="file-with-tags")
    file_tags = await file_model.tags.all()

    assert {tag.name for tag in tags} == {"document", "report"}
    assert all(tag.id for tag in tags)
    assert {tag.name for tag in file_tags} == {"document", "report"}


@pytest.mark.asyncio
async def test_file_repository_counts_by_category_with_filters(settings) -> None:
    repository = FileRepositoryImpl()
    folder = await FolderModel.create(
        id="folder-1",
        name="Folder 1",
        icon_type="default",
        description="",
        modified=datetime.now(UTC),
    )
    modified = datetime.now(UTC)

    await FileModel.create(
        id="document-1",
        name="report.pdf",
        file_type=FileType.PDF.value,
        category=FileCategory.DOCUMENT.value,
        size=100,
        modified=modified,
        path="/library/report.pdf",
        storage_id="local",
        access_state="available",
        folder=folder,
    )
    await FileModel.create(
        id="image-1",
        name="photo.jpg",
        file_type=FileType.JPG.value,
        category=FileCategory.IMAGE.value,
        size=10,
        modified=modified,
        path="/library/photo.jpg",
        storage_id="local",
        access_state="available",
        folder=folder,
    )
    await FileModel.create(
        id="other-folder-image",
        name="other.jpg",
        file_type=FileType.JPG.value,
        category=FileCategory.IMAGE.value,
        size=100,
        modified=modified,
        path="/other/other.jpg",
        storage_id="local",
        access_state="available",
    )

    counter = await repository.count_by_category(
        folder_id="folder-1",
        min_size=50,
        max_size=200,
    )
    total = await repository.count(
        folder_id="folder-1",
        min_size=50,
        max_size=200,
    )

    assert counter == {
        FileCategory.DOCUMENT.value: 1,
        FileCategory.IMAGE.value: 0,
        FileCategory.VIDEO.value: 0,
    }
    assert total == 1
