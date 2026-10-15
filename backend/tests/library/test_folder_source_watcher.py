from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from fileseek.config.settings import Settings
from fileseek.features.library.application.commands import AddFileCommand
from fileseek.features.library.application.dto import AddFileResult
from fileseek.features.library.application.ports import (
    FolderSourceRootPort,
    SourceMetadata,
    WatchableSourceRoot,
)
from fileseek.features.library.application.use_cases.add_file import AddFileUseCase
from fileseek.features.library.domain.entities import File, Folder, FolderSourceBinding
from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.features.library.infrastructure.watcher import (
    FolderSourceWatcherService,
    watchfiles_stream,
)
from fileseek.features.settings.infrastructure.source_access import LocalSourceFile
from fileseek.features.tasks.domain.entities import Task, TaskStatus
from fileseek.features.tasks.domain.ports import ClassifierLabelSnapshot
from fileseek.shared.domain.exceptions import FileNotSupportError

type FileChangeSet = set[tuple[int, str]]


class FakeBindingRepository:
    def __init__(self, bindings: list[FolderSourceBinding]) -> None:
        self.bindings = bindings

    async def get_by_id(self, binding_id: str) -> FolderSourceBinding | None:
        return next((item for item in self.bindings if item.id == binding_id), None)

    async def list_by_folder(self, folder_id: str) -> list[FolderSourceBinding]:
        return [item for item in self.bindings if item.folder_id == folder_id]

    async def list_enabled(self) -> list[FolderSourceBinding]:
        return [item for item in self.bindings if item.enabled]

    async def list_all(self) -> list[FolderSourceBinding]:
        return list(self.bindings)

    async def save(self, binding: FolderSourceBinding) -> None:
        self.bindings = [binding if item.id == binding.id else item for item in self.bindings]

    async def delete(self, binding_id: str) -> None:
        self.bindings = [item for item in self.bindings if item.id != binding_id]


class FakeSeenRepository:
    def __init__(self, paths: set[str] | None = None) -> None:
        self.entries: dict[str, dict[str, str]] = {}
        if paths:
            self.entries["binding-1"] = dict.fromkeys(paths, "seen")

    async def list_paths(self, binding_id: str) -> set[str]:
        return set(self.entries.get(binding_id, {}))

    async def save(self, seen) -> None:
        self.entries.setdefault(seen.binding_id, {})[seen.source_path] = seen.outcome

    async def delete_path(self, binding_id: str, source_path: str) -> None:
        self.entries.get(binding_id, {}).pop(source_path, None)

    async def replace_paths(
        self,
        binding_id: str,
        source_paths,
    ) -> None:
        self.entries[binding_id] = dict.fromkeys(source_paths, "seen")


class FakeRootResolver(FolderSourceRootPort):
    def __init__(
        self,
        storage_root: Path,
        *,
        paths: tuple[str, ...] = (),
    ) -> None:
        self.storage_root = storage_root
        self.paths = paths

    async def resolve(
        self,
        storage_id: str,
        source_path: str,
    ) -> WatchableSourceRoot:
        return WatchableSourceRoot(
            storage_id=storage_id,
            source_path=source_path,
            storage_root=self.storage_root,
            filesystem_path=self.storage_root / source_path,
        )

    async def list_file_paths(
        self,
        root: WatchableSourceRoot,
        *,
        recursive: bool,
    ) -> tuple[str, ...]:
        _ = recursive
        return self.paths


class FakeImporter:
    def __init__(
        self,
        errors: list[Exception] | None = None,
    ) -> None:
        self.errors = list(errors or [])
        self.commands: list[AddFileCommand] = []
        self.attempted = asyncio.Event()
        self.completed = asyncio.Event()

    async def execute(self, command: AddFileCommand) -> AddFileResult:
        self.commands.append(command)
        self.attempted.set()
        if self.errors:
            error = self.errors.pop(0)
            raise error
        self.completed.set()
        return AddFileResult(file_id="file-1", task_id="task-1")


class FakeEventStream:
    def __init__(self, changes: list[FileChangeSet]) -> None:
        self.changes = list(changes)

    def __aiter__(self) -> AsyncIterable[FileChangeSet]:
        return self

    async def __anext__(self) -> FileChangeSet:
        if self.changes:
            return self.changes.pop(0)
        raise StopAsyncIteration


class IntegrationFileRepository:
    def __init__(self) -> None:
        self.files: dict[str, File] = {}

    async def get_by_id(self, file_id: str) -> File | None:
        return self.files.get(file_id)

    async def save(self, file: File) -> None:
        self.files[file.id] = file


class IntegrationFolderRepository:
    async def get_by_id(self, folder_id: str):
        _ = folder_id
        return Folder(
            id="folder-1",
            name="工作资料",
            icon_type="folder",
            description="",
            modified=datetime.now(UTC),
        )


class IntegrationTaskManager:
    def __init__(self) -> None:
        self.tasks: list[Task] = []
        self.created = asyncio.Event()

    async def create(self, task: Task) -> Task:
        self.tasks.append(task)
        self.created.set()
        return task


class IntegrationLabelProvider:
    async def get_snapshot(self) -> ClassifierLabelSnapshot:
        return ClassifierLabelSnapshot(
            document_labels=("合同",),
            image_labels=(),
            video_labels=(),
            version="integration",
        )


class IntegrationFileSource:
    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root

    async def resolve(self, storage_id: str, source_path: str) -> LocalSourceFile:
        _ = storage_id
        return LocalSourceFile(self.storage_root / source_path)

    async def read_metadata(
        self,
        storage_id: str,
        source_path: str,
    ) -> SourceMetadata:
        source = await self.resolve(storage_id, source_path)
        metadata = source.stat()
        return SourceMetadata(
            size=int(metadata["size"]),
            modified=datetime.fromtimestamp(float(metadata["mtime"]), tz=UTC),
        )


class IntegrationRootResolver(FakeRootResolver):
    async def list_file_paths(
        self,
        root: WatchableSourceRoot,
        *,
        recursive: bool,
    ) -> tuple[str, ...]:
        _ = recursive
        paths = (path for path in root.filesystem_path.rglob("*") if path.is_file())
        return tuple(path.relative_to(root.storage_root).as_posix() for path in paths)


class ReadySignallingStream:
    def __init__(self, stream, ready: asyncio.Event) -> None:
        self.stream = stream
        self.ready = ready

    def __aiter__(self):
        return self

    async def __anext__(self) -> FileChangeSet:
        self.ready.set()
        return await self.stream.__anext__()


class LateArrivalRootResolver(FakeRootResolver):
    def __init__(self, storage_root: Path, source_path: str) -> None:
        super().__init__(storage_root)
        self.source_path = source_path
        self.scan_count = 0
        self.second_scan = asyncio.Event()

    async def list_file_paths(
        self,
        root: WatchableSourceRoot,
        *,
        recursive: bool,
    ) -> tuple[str, ...]:
        _ = root, recursive
        self.scan_count += 1
        if self.scan_count == 1:
            return ()
        self.second_scan.set()
        return (self.source_path,)


class IntegrationSeenRepository(FakeSeenRepository):
    def __init__(self) -> None:
        super().__init__()
        self.imported = asyncio.Event()
        self.imported_count = 0

    async def save(self, seen) -> None:
        await super().save(seen)
        if seen.outcome == "imported":
            self.imported_count += 1
            if self.imported_count == 2:
                self.imported.set()


def make_service(
    tmp_path: Path,
    changes: list[FileChangeSet],
    *,
    importer_errors: list[Exception] | None = None,
    seen_paths: set[str] | None = None,
    catchup_paths: tuple[str, ...] = (),
    scan_interval: float = 30.0,
) -> tuple[FolderSourceWatcherService, FakeBindingRepository, FakeImporter]:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(exist_ok=True)
    binding = FolderSourceBinding(
        id="binding-1",
        folder_id="folder-1",
        storage_id="nas",
        source_path="watch",
    )
    binding_repo = FakeBindingRepository([binding])
    importer = FakeImporter(importer_errors)

    def stream_factory(
        filesystem_path: Path,
        recursive: bool,
        stop_event: asyncio.Event,
    ) -> FakeEventStream:
        _ = filesystem_path
        _ = recursive
        _ = stop_event
        return FakeEventStream(changes)

    service = FolderSourceWatcherService(
        binding_repo=binding_repo,
        seen_repo=FakeSeenRepository(seen_paths),
        root_resolver=FakeRootResolver(storage_root, paths=catchup_paths),
        add_file_use_case=importer,  # type: ignore[arg-type]
        settings=Settings(
            lib_root=tmp_path / "library",
            folder_watch_settle_seconds=0,
            folder_watch_stable_checks=2,
            folder_watch_scan_interval_seconds=scan_interval,
            folder_watch_max_retries=2,
            task_drain_timeout=0.5,
        ),
        stream_factory=stream_factory,
    )
    return service, binding_repo, importer


async def wait_for(event: asyncio.Event) -> None:
    await asyncio.wait_for(event.wait(), timeout=1)


@pytest.mark.asyncio
async def test_watcher_imports_new_stable_file_once(tmp_path: Path) -> None:
    directory = tmp_path / "storage" / "watch"
    directory.mkdir(parents=True)
    source_file = directory / "report.pdf"
    source_file.write_text("content")
    service, binding_repo, importer = make_service(
        tmp_path,
        [
            {(1, str(source_file))},
            {(2, str(source_file))},
        ],
    )

    await service.start()
    await wait_for(importer.completed)
    await service.stop()

    assert len(importer.commands) == 1
    assert importer.commands[0].folder_id == "folder-1"
    assert importer.commands[0].storage_id == "nas"
    assert importer.commands[0].path == "watch/report.pdf"
    assert binding_repo.bindings[0].watch_status == "watching"


@pytest.mark.asyncio
async def test_watcher_clears_seen_when_file_is_deleted(tmp_path: Path) -> None:
    directory = tmp_path / "storage" / "watch"
    directory.mkdir(parents=True)
    source_file = directory / "report.pdf"
    source_file.write_text("content")
    service, _, _ = make_service(
        tmp_path,
        [],
        seen_paths={"watch/report.pdf"},
    )
    binding = FolderSourceBinding(
        id="binding-1",
        folder_id="folder-1",
        storage_id="nas",
        source_path="watch",
    )
    root = await service.root_resolver.resolve("nas", "watch")

    await service._handle_change(binding, root, 3, source_file)

    seen_repository = service.seen_repo
    assert isinstance(seen_repository, FakeSeenRepository)
    assert await seen_repository.list_paths("binding-1") == set()


@pytest.mark.asyncio
async def test_watcher_reimports_recreated_file_at_same_path(tmp_path: Path) -> None:
    directory = tmp_path / "storage" / "watch"
    directory.mkdir(parents=True)
    source_file = directory / "report.pdf"
    source_file.write_text("recreated content")
    service, _, importer = make_service(
        tmp_path,
        [],
        seen_paths={"watch/report.pdf"},
    )
    binding = FolderSourceBinding(
        id="binding-1",
        folder_id="folder-1",
        storage_id="nas",
        source_path="watch",
    )
    root = await service.root_resolver.resolve("nas", "watch")

    await service.start()
    await service._handle_change(binding, root, 3, source_file)
    await service._handle_change(binding, root, 1, source_file)
    await wait_for(importer.completed)
    await service.stop()

    assert [command.path for command in importer.commands] == ["watch/report.pdf"]


@pytest.mark.asyncio
async def test_watcher_filters_hidden_partial_and_nonrecursive_files(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "storage" / "watch"
    directory.mkdir(parents=True)
    hidden = directory / ".DS_Store"
    partial = directory / "download.part"
    child = directory / "child" / "report.pdf"
    normal = directory / "report.pdf"
    for path in (hidden, partial, child, normal):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content")

    assert not FolderSourceWatcherService._is_processable_file(hidden)
    assert not FolderSourceWatcherService._is_processable_file(partial)
    assert FolderSourceWatcherService._is_processable_file(normal)

    service, _, _ = make_service(tmp_path, [])
    binding = FolderSourceBinding(
        id="binding-2",
        folder_id="folder-1",
        storage_id="nas",
        source_path="watch",
        recursive=False,
    )
    root = await FakeRootResolver(tmp_path / "storage").resolve("nas", "watch")

    await service._handle_change(binding, root, 1, child)

    assert service._queue.qsize() == 0


@pytest.mark.asyncio
async def test_missing_file_is_not_imported(tmp_path: Path) -> None:
    service, _, importer = make_service(tmp_path, [])
    missing_path = tmp_path / "missing.pdf"

    assert not await service._is_stable(missing_path)
    assert importer.commands == []


@pytest.mark.asyncio
async def test_changed_file_is_not_stable(tmp_path: Path) -> None:
    service, _, importer = make_service(tmp_path, [])
    stats = [(1, 1), (1, 2)]

    def stat(_: Path) -> tuple[int, int] | None:
        return stats.pop(0)

    service._stat = stat  # type: ignore[method-assign]
    assert not await service._is_stable(tmp_path / "changing.pdf")
    assert importer.commands == []


@pytest.mark.asyncio
async def test_stability_requires_consecutive_samples(tmp_path: Path) -> None:
    service, _, importer = make_service(tmp_path, [])
    stats = [(1, 1), (1, 1), (2, 2)]

    def stat(_: Path) -> tuple[int, int] | None:
        return stats.pop(0)

    service._stat = stat  # type: ignore[method-assign]
    assert not await service._is_stable(tmp_path / "pausing.pdf")
    assert importer.commands == []


@pytest.mark.asyncio
async def test_unstable_file_is_retried_until_stable(tmp_path: Path) -> None:
    directory = tmp_path / "storage" / "watch"
    directory.mkdir(parents=True)
    source_file = directory / "writing.pdf"
    source_file.write_text("first")
    service, _, importer = make_service(
        tmp_path,
        [{(1, str(source_file))}],
    )
    states = iter(["unstable", "stable"])

    async def stability(_: Path) -> str:
        return next(states)

    service._stability = stability  # type: ignore[method-assign]

    await service.start()
    await wait_for(importer.completed)
    await service.stop()

    assert [command.path for command in importer.commands] == ["watch/writing.pdf"]


@pytest.mark.asyncio
async def test_periodic_scan_imports_file_when_event_is_missed(tmp_path: Path) -> None:
    directory = tmp_path / "storage" / "watch"
    directory.mkdir(parents=True)
    source_file = directory / "missed.pdf"
    source_file.write_text("missed event")
    service, _, importer = make_service(tmp_path, [], scan_interval=0.01)
    late_resolver = LateArrivalRootResolver(tmp_path / "storage", "watch/missed.pdf")
    service.root_resolver = late_resolver  # type: ignore[assignment]

    await service.start()
    await wait_for(late_resolver.second_scan)
    await wait_for(importer.completed)
    await service.stop()

    assert [command.path for command in importer.commands] == ["watch/missed.pdf"]


@pytest.mark.asyncio
async def test_watcher_retries_transient_failures(tmp_path: Path) -> None:
    directory = tmp_path / "storage" / "watch"
    directory.mkdir(parents=True)
    source_file = directory / "report.pdf"
    source_file.write_text("content")
    service, binding_repo, importer = make_service(
        tmp_path,
        [{(1, str(source_file))}],
        importer_errors=[SourceUnavailableError("offline"), OSError("busy")],
    )

    await service.start()
    await wait_for(importer.completed)
    await service.stop()

    assert len(importer.commands) == 3
    assert binding_repo.bindings[0].watch_status == "watching"


@pytest.mark.asyncio
async def test_watcher_records_unsupported_file_health(tmp_path: Path) -> None:
    directory = tmp_path / "storage" / "watch"
    directory.mkdir(parents=True)
    source_file = directory / "report.pdf"
    source_file.write_text("content")
    service, binding_repo, importer = make_service(
        tmp_path,
        [{(1, str(source_file))}],
        importer_errors=[FileNotSupportError("不支持的文件类型")],
    )

    await service.start()
    await wait_for(importer.attempted)
    await service.stop()

    assert binding_repo.bindings[0].watch_status == "error"
    assert binding_repo.bindings[0].last_error == "不支持的文件类型"


@pytest.mark.asyncio
async def test_watcher_imports_offline_arrivals_on_restart(tmp_path: Path) -> None:
    service, _, importer = make_service(
        tmp_path,
        [],
        catchup_paths=("watch/report.pdf",),
    )
    (tmp_path / "storage" / "watch").mkdir(parents=True)
    (tmp_path / "storage" / "watch" / "report.pdf").write_text("offline")

    await service.start()
    await wait_for(importer.completed)
    await service.stop()

    assert [command.path for command in importer.commands] == ["watch/report.pdf"]


@pytest.mark.asyncio
async def test_first_binding_scan_imports_existing_supported_file(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "storage" / "watch"
    directory.mkdir(parents=True)
    (directory / "existing.md").write_text("# Existing file\n", encoding="utf-8")
    service, _, importer = make_service(
        tmp_path,
        [],
        catchup_paths=("watch/existing.md",),
    )

    await service.start()
    await wait_for(importer.completed)
    await service.stop()

    assert [command.path for command in importer.commands] == ["watch/existing.md"]


@pytest.mark.asyncio
async def test_watcher_reconciles_dynamic_binding_changes(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path, [])

    await service.start()
    assert service.watching_binding_ids() == {"binding-1"}

    await service.remove_binding("binding-1")
    assert service.watching_binding_ids() == set()

    await service.reload_binding("binding-1")
    assert service.watching_binding_ids() == {"binding-1"}
    await service.stop()


@pytest.mark.asyncio
async def test_watcher_marks_unavailable_roots(tmp_path: Path) -> None:
    class UnavailableRootResolver(FakeRootResolver):
        async def resolve(
            self,
            storage_id: str,
            source_path: str,
        ) -> WatchableSourceRoot:
            raise SourceUnavailableError("来源目录不可访问")

    binding = FolderSourceBinding(
        id="binding-1",
        folder_id="folder-1",
        storage_id="nas",
        source_path="watch",
    )
    binding_repo = FakeBindingRepository([binding])
    service = FolderSourceWatcherService(
        binding_repo=binding_repo,
        seen_repo=FakeSeenRepository(),
        root_resolver=UnavailableRootResolver(tmp_path),
        add_file_use_case=FakeImporter(),  # type: ignore[arg-type]
        settings=Settings(
            lib_root=tmp_path / "library",
            folder_watch_settle_seconds=0,
        ),
        stream_factory=lambda *args: FakeEventStream([]),
    )

    await service.start()
    await asyncio.sleep(0)
    await service.stop()

    assert binding_repo.bindings[0].watch_status == "unavailable"


@pytest.mark.asyncio
async def test_real_filesystem_event_registers_file_and_queues_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "storage"
    watch_directory = storage_root / "watch"
    watch_directory.mkdir(parents=True)
    existing_file = watch_directory / "existing.md"
    existing_file.write_text("# Existing arrival\n", encoding="utf-8")
    unsupported_file = watch_directory / "ignored.bin"
    unsupported_file.write_bytes(b"\x00\x01 unrecognized")
    binding = FolderSourceBinding(
        id="binding-1",
        folder_id="folder-1",
        storage_id="local",
        source_path="watch",
    )
    binding_repository = FakeBindingRepository([binding])
    seen_repository = IntegrationSeenRepository()
    root_resolver = IntegrationRootResolver(storage_root)
    settings = Settings(
        lib_root=tmp_path / "library",
        db_path=tmp_path / "app.db",
        vector_db_path=tmp_path / "vectors",
        embedding_model_cache_dir=tmp_path / "models",
        recycle_dir=tmp_path / "recycle",
        temp_dir=tmp_path / "temp",
        folder_watch_settle_seconds=0,
    )
    monkeypatch.setattr(
        "fileseek.features.library.application.use_cases.add_file.get_settings",
        lambda: settings,
    )
    file_repository = IntegrationFileRepository()
    task_manager = IntegrationTaskManager()
    add_file_use_case = AddFileUseCase(
        file_repository,
        IntegrationFolderRepository(),
        task_manager,
        IntegrationFileSource(storage_root),
        IntegrationLabelProvider(),
    )
    watcher_ready = asyncio.Event()

    def stream_factory(
        filesystem_path: Path,
        recursive: bool,
        stop_event: asyncio.Event,
    ):
        return ReadySignallingStream(
            watchfiles_stream(filesystem_path, recursive, stop_event),
            watcher_ready,
        )

    service = FolderSourceWatcherService(
        binding_repo=binding_repository,
        seen_repo=seen_repository,
        root_resolver=root_resolver,
        add_file_use_case=add_file_use_case,
        settings=settings,
        stream_factory=stream_factory,
    )

    await service.start()
    await asyncio.wait_for(watcher_ready.wait(), timeout=2)
    source_file = watch_directory / "arrival.md"
    source_file.write_text("# Watched arrival\n", encoding="utf-8")
    await asyncio.wait_for(seen_repository.imported.wait(), timeout=2)
    await service.stop()

    assert set(file_repository.files) == {
        sha256(source_file.read_bytes()).hexdigest(),
        sha256(existing_file.read_bytes()).hexdigest(),
    }
    assert [task.file.path for task in task_manager.tasks] == [
        "watch/existing.md",
        "watch/arrival.md",
    ]
    assert task_manager.tasks[0].status is TaskStatus.QUEUED
    assert all(task.status is TaskStatus.QUEUED for task in task_manager.tasks)
    assert all(task.file.folder_id == "folder-1" for task in task_manager.tasks)
    assert all(task.file.storage_id == "local" for task in task_manager.tasks)
    assert seen_repository.entries["binding-1"]["watch/arrival.md"] == "imported"
    assert seen_repository.entries["binding-1"]["watch/existing.md"] == "imported"
    assert seen_repository.entries["binding-1"]["watch/ignored.bin"] == "unsupported"
