from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.application.handlers import FileHandlerRegistry
from fileseek.features.tasks.application.processor import TaskProcessor
from fileseek.features.tasks.domain.entities import Task
from fileseek.features.tasks.domain.ports import ProgressReporter
from fileseek.shared.domain.file_types import FileCategory, FileType


class FakeHandler:
    def supports(self, file_type: FileType) -> bool:
        return file_type is FileType.TXT

    def process(self, task: Task, progress: ProgressReporter) -> None:
        _ = task, progress


class FakeVectorIndex:
    def update_file_tags(self, file_id: str, tags: list[str]) -> None:
        _ = file_id, tags


def test_task_processor_cleans_temp_cache_and_keeps_source(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    cache = tmp_path / "cache.txt"
    source.write_text("source", encoding="utf-8")
    cache.write_text("cache", encoding="utf-8")
    file = File(
        id="file-1",
        name="source.txt",
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path=str(source),
        storage_id="local",
    )
    task = Task(
        id="task-1",
        file=file,
        metadata={"temp_path": str(cache)},
    )
    processor = TaskProcessor(
        handler_registry=FileHandlerRegistry(handlers=[FakeHandler()]),
        vector_index=FakeVectorIndex(),
    )

    processor.process(task, FakeHandler())

    assert source.exists()
    assert not cache.exists()
