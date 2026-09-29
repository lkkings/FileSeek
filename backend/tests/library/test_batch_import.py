from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from fileseek.features.library.application.commands import (
    AddFileCommand,
    BatchImportCommand,
    BatchImportItemCommand,
)
from fileseek.features.library.application.dto import AddFileResult
from fileseek.features.library.application.use_cases import (
    BatchImportSessionManager,
)
from fileseek.features.library.domain.entities import File
from fileseek.features.library.infrastructure import (
    TaskRepositoryImportProgressPort,
)
from fileseek.features.tasks.domain.entities import Task, TaskStage, TaskStatus
from fileseek.shared.domain.exceptions import FileAlreadyExistsError
from fileseek.shared.domain.file_types import FileCategory, FileType


class FakeAddFileUseCase:
    def __init__(self) -> None:
        self.commands: list[AddFileCommand] = []

    async def execute(self, command: AddFileCommand) -> AddFileResult:
        self.commands.append(command)
        if command.path == "duplicate.pdf":
            raise FileAlreadyExistsError("文件已经存在")
        return AddFileResult(
            file_id=f"file-{len(self.commands)}",
            task_id=f"task-{len(self.commands)}",
        )


async def collect_events(manager: BatchImportSessionManager, import_id: str, last_id: int = 0):
    return [event async for event in manager.subscribe(import_id, last_id)]


@pytest.mark.asyncio
async def test_batch_import_continues_after_item_failure() -> None:
    add_file = FakeAddFileUseCase()
    manager = BatchImportSessionManager(add_file)
    command = BatchImportCommand(
        folder_id="folder-1",
        items=(
            BatchImportItemCommand(path="first.pdf", storage_id="local"),
            BatchImportItemCommand(path="duplicate.pdf", storage_id="local"),
            BatchImportItemCommand(path="third.pdf", storage_id="nas1"),
        ),
    )

    started = await manager.start(command)
    events = await collect_events(manager, started.import_id)
    await manager.close()

    assert started.total == 3
    assert [event.type for event in events] == [
        "batch_started",
        "item_started",
        "item_registered",
        "item_completed",
        "item_started",
        "item_failed",
        "item_started",
        "item_registered",
        "item_completed",
        "batch_completed",
    ]
    assert events[-1].payload == {"total": 3, "succeeded": 2, "failed": 1}
    failed_event = next(event for event in events if event.type == "item_failed")
    assert failed_event.payload["error"] == "文件已经存在"
    assert [command.path for command in add_file.commands] == [
        "first.pdf",
        "duplicate.pdf",
        "third.pdf",
    ]


@pytest.mark.asyncio
async def test_batch_import_completes_when_every_item_fails() -> None:
    add_file = FakeAddFileUseCase()
    manager = BatchImportSessionManager(add_file)
    command = BatchImportCommand(
        folder_id="folder-1",
        items=(
            BatchImportItemCommand(path="duplicate.pdf"),
            BatchImportItemCommand(path="duplicate.pdf"),
        ),
    )

    started = await manager.start(command)
    events = await collect_events(manager, started.import_id)
    await manager.close()

    assert events[-1].type == "batch_completed"
    assert events[-1].payload == {"total": 2, "succeeded": 0, "failed": 2}


@pytest.mark.asyncio
async def test_batch_import_replays_after_disconnect() -> None:
    manager = BatchImportSessionManager(FakeAddFileUseCase())
    command = BatchImportCommand(
        folder_id="folder-1",
        items=(BatchImportItemCommand(path="first.pdf"),),
    )

    started = await manager.start(command)
    first_events = []
    async for event in manager.subscribe(started.import_id):
        first_events.append(event)
        if len(first_events) == 2:
            break

    remaining_events = await collect_events(manager, started.import_id, 2)
    await manager.close()

    assert [event.id for event in first_events] == [1, 2]
    assert remaining_events[0].id == 3
    assert remaining_events[-1].type == "batch_completed"


@pytest.mark.asyncio
async def test_batch_import_expires_completed_sessions() -> None:
    manager = BatchImportSessionManager(
        FakeAddFileUseCase(),
        session_retention_seconds=0,
    )
    command = BatchImportCommand(
        folder_id="folder-1",
        items=(BatchImportItemCommand(path="first.pdf"),),
    )

    started = await manager.start(command)
    await collect_events(manager, started.import_id)
    await manager.start(command)

    with pytest.raises(KeyError):
        await collect_events(manager, started.import_id)

    await manager.close()


@pytest.mark.asyncio
async def test_task_repository_progress_port_maps_task_snapshot() -> None:
    file = File(
        id="file-1",
        name="report.pdf",
        file_type=FileType.PDF,
        category=FileCategory.DOCUMENT,
        size=10,
        modified=datetime.now(UTC),
        path="/storage/report.pdf",
    )
    task = Task(
        id="task-1",
        file=file,
        status=TaskStatus.PROCESSING,
        completed_count=3,
        total_count=10,
        stage=TaskStage.ENCODED,
    )

    class FakeTaskRepository:
        async def get_by_id(self, task_id: str) -> Task | None:
            return task if task_id == "task-1" else None

    port = TaskRepositoryImportProgressPort(FakeTaskRepository())

    snapshots = await port.get_snapshots(("task-1", "missing"))

    assert asdict(snapshots["task-1"]) == {
        "task_id": "task-1",
        "file_id": "file-1",
        "status": "processing",
        "progress": "3/10",
        "completed_count": 3,
        "total_count": 10,
        "stage": "encoded",
        "error_message": None,
    }
    assert "missing" not in snapshots
