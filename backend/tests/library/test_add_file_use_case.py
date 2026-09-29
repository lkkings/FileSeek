from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fileseek.config.settings import Settings
from fileseek.features.library.application.commands import AddFileCommand
from fileseek.features.library.application.ports import SourceMetadata
from fileseek.features.library.application.use_cases.add_file import AddFileUseCase
from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.features.settings.domain.entities import StorageLocation
from fileseek.features.settings.infrastructure.source_access import (
    LocalSourceFile,
    StorageSourceResolver,
)
from fileseek.features.tasks.domain.entities import Task
from fileseek.features.tasks.domain.ports import (
    ClassifierLabelSnapshot,
)
from fileseek.shared.domain.exceptions import FileAlreadyExistsError, FileNotSupportError
from fileseek.shared.domain.file_types import FileType


class FakeFileSource:
    def __init__(self, missing: bool = False) -> None:
        self.missing = missing

    async def resolve(self, storage_id: str, source_path: str):
        _ = storage_id
        if self.missing:
            raise SourceUnavailableError("来源文件不可访问")
        return LocalSourceFile(Path(source_path))

    async def read_metadata(
        self,
        storage_id: str,
        source_path: str,
    ) -> SourceMetadata:
        source = await self.resolve(storage_id, source_path)
        stat = source.stat()
        return SourceMetadata(
            size=int(stat["size"]),
            modified=datetime.fromtimestamp(float(stat["mtime"]), tz=UTC),
        )


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


class FakeFileRepository:
    def __init__(self) -> None:
        self.files: dict[str, File] = {}

    async def get_by_id(self, file_id: str) -> File | None:
        return self.files.get(file_id)

    async def save(self, file: File) -> None:
        self.files[file.id] = file


class FakeFolderRepository:
    async def get_by_id(self, folder_id: str):
        _ = folder_id
        return

class FakeTaskManager:
    def __init__(self) -> None:
        self.tasks: list[Task] = []

    async def create(self, task: Task) -> Task:
        self.tasks.append(task)
        return task


class FakeLabelProvider:
    def __init__(self) -> None:
        self.snapshot = ClassifierLabelSnapshot(
            document_labels=("合同",),
            image_labels=("照片",),
            video_labels=("课程",),
            version="version-1",
        )

    async def get_snapshot(self) -> ClassifierLabelSnapshot:
        return self.snapshot


def _settings(root: Path) -> Settings:
    return Settings(
        lib_root=root,
        db_path=root / "app.db",
        vector_db_path=root / "vectors",
        embedding_model_cache_dir=root / "models",
        recycle_dir=root / "recycle",
        temp_dir=root / "temp",
    )


@pytest.mark.asyncio
async def test_add_file_registers_source_without_library_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("indexed content", encoding="utf-8")
    settings = _settings(tmp_path / "library")
    monkeypatch.setattr(
        "fileseek.features.library.application.use_cases.add_file.get_settings",
        lambda: settings,
    )
    file_repository = FakeFileRepository()
    task_manager = FakeTaskManager()
    use_case = AddFileUseCase(
        file_repository,
        FakeFolderRepository(),
        task_manager,
        FakeFileSource(),
        FakeLabelProvider(),
    )

    result = await use_case.execute(
        AddFileCommand(folder_id="", path=str(source), storage_id="local")
    )
    file_id = result.file_id

    file = file_repository.files[file_id]
    assert file.path == str(source)
    assert file.storage_id == "local"
    assert file.access_state == "available"
    assert not list((settings.lib_root / "documents").rglob("*.txt"))
    assert len(task_manager.tasks) == 1
    assert task_manager.tasks[0].id == result.task_id
    assert task_manager.tasks[0].metadata["temp_path"]
    assert task_manager.tasks[0].metadata["classifier_label_version"] == "version-1"
    assert task_manager.tasks[0].metadata["classifier_labels"]["document"] == ["合同"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content", "file_type"),
    [
        ("source.md", "# Indexed content\n", FileType.MARKDOWN),
        ("source.pdf", b"%PDF-1.4\n%%EOF\n", FileType.PDF),
    ],
)
async def test_add_file_preserves_document_extension_for_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    content: str | bytes,
    file_type: FileType,
) -> None:
    source = tmp_path / filename
    if isinstance(content, str):
        source.write_text(content, encoding="utf-8")
    else:
        source.write_bytes(content)
    settings = _settings(tmp_path / "library")
    monkeypatch.setattr(
        "fileseek.features.library.application.use_cases.add_file.get_settings",
        lambda: settings,
    )
    file_repository = FakeFileRepository()
    task_manager = FakeTaskManager()
    use_case = AddFileUseCase(
        file_repository,
        FakeFolderRepository(),
        task_manager,
        FakeFileSource(),
        FakeLabelProvider(),
    )

    result = await use_case.execute(
        AddFileCommand(folder_id="", path=str(source), storage_id="local")
    )

    temp_path = Path(task_manager.tasks[0].metadata["temp_path"])
    assert temp_path.suffix == Path(filename).suffix
    assert file_repository.files[result.file_id].file_type is file_type


@pytest.mark.asyncio
async def test_add_file_rejects_removed_document_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.rtf"
    source.write_bytes(b"{\\rtf1}")
    settings = _settings(tmp_path / "library")
    monkeypatch.setattr(
        "fileseek.features.library.application.use_cases.add_file.get_settings",
        lambda: settings,
    )
    file_repository = FakeFileRepository()
    task_manager = FakeTaskManager()
    use_case = AddFileUseCase(
        file_repository,
        FakeFolderRepository(),
        task_manager,
        FakeFileSource(),
        FakeLabelProvider(),
    )

    with pytest.raises(FileNotSupportError):
        await use_case.execute(
            AddFileCommand(folder_id="", path=str(source), storage_id="local")
        )

    assert not file_repository.files
    assert not task_manager.tasks


@pytest.mark.asyncio
async def test_add_file_registers_mounted_nas_relative_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nas_root = tmp_path / "nas"
    source = nas_root / "source.txt"
    source.parent.mkdir()
    source.write_text("nas indexed content", encoding="utf-8")
    settings = _settings(tmp_path / "library")
    monkeypatch.setattr(
        "fileseek.features.library.application.use_cases.add_file.get_settings",
        lambda: settings,
    )
    file_repository = FakeFileRepository()
    task_manager = FakeTaskManager()
    resolver = StorageSourceResolver(
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
    )
    use_case = AddFileUseCase(
        file_repository,
        FakeFolderRepository(),
        task_manager,
        resolver,
        FakeLabelProvider(),
    )

    result = await use_case.execute(
        AddFileCommand(folder_id="", path="source.txt", storage_id="nas1")
    )
    file_id = result.file_id

    file = file_repository.files[file_id]
    assert file.path == "source.txt"
    assert file.storage_id == "nas1"
    assert file.access_state == "available"
    assert source.read_text(encoding="utf-8") == "nas indexed content"
    assert not list((settings.lib_root / "documents").rglob("*.txt"))
    assert len(task_manager.tasks) == 1
    assert task_manager.tasks[0].id == result.task_id


@pytest.mark.asyncio
async def test_add_file_rejects_duplicate_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("same", encoding="utf-8")
    second.write_text("same", encoding="utf-8")
    monkeypatch.setattr(
        "fileseek.features.library.application.use_cases.add_file.get_settings",
        lambda: _settings(tmp_path / "library"),
    )
    file_repository = FakeFileRepository()
    task_manager = FakeTaskManager()
    use_case = AddFileUseCase(
        file_repository,
        FakeFolderRepository(),
        task_manager,
        FakeFileSource(),
        FakeLabelProvider(),
    )
    await use_case.execute(
        AddFileCommand(folder_id="", path=str(first), storage_id="local")
    )

    with pytest.raises(FileAlreadyExistsError):
        await use_case.execute(
            AddFileCommand(folder_id="", path=str(second), storage_id="local")
        )

    assert len(file_repository.files) == 1
    assert len(task_manager.tasks) == 1


@pytest.mark.asyncio
async def test_add_file_rejects_missing_source(tmp_path: Path) -> None:
    use_case = AddFileUseCase(
        FakeFileRepository(),
        FakeFolderRepository(),
        FakeTaskManager(),
        FakeFileSource(missing=True),
        FakeLabelProvider(),
    )

    with pytest.raises(SourceUnavailableError):
        await use_case.execute(
            AddFileCommand(
                folder_id="",
                path=str(tmp_path / "missing.txt"),
                storage_id="local",
            )
        )
