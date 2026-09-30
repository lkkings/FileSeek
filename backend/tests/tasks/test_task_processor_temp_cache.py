from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.application.compute import TaskResult, TaskSpec
from fileseek.features.tasks.application.handlers import FileHandlerRegistry
from fileseek.features.tasks.application.processor import TaskProcessor
from fileseek.features.tasks.domain.entities import Task
from fileseek.features.tasks.domain.ports import ProgressReporter
from fileseek.features.tasks.infrastructure.worker import make_task_request_handler
from fileseek.shared.domain.file_types import FileCategory, FileType


class FakeHandler:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def supports(self, file_type: FileType) -> bool:
        return file_type is FileType.TXT

    def compute(self, spec: TaskSpec, progress: ProgressReporter) -> TaskResult:
        _ = spec, progress
        if self.fail:
            raise ValueError("parse failed")
        return TaskResult.empty()


def _spec(tmp_path: Path) -> tuple[TaskSpec, Path, Path]:
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
    task = Task(id="task-1", file=file, metadata={"temp_path": str(cache)})
    return TaskProcessor.build_spec(task), source, cache


def test_worker_cleans_temp_cache_and_keeps_source(tmp_path: Path) -> None:
    spec, source, cache = _spec(tmp_path)
    handle = make_task_request_handler(FileHandlerRegistry(handlers=[FakeHandler()]))

    handle(spec, lambda progress: None)

    assert source.exists()
    assert not cache.exists()


def test_worker_cleans_temp_cache_when_compute_fails(tmp_path: Path) -> None:
    spec, source, cache = _spec(tmp_path)
    handle = make_task_request_handler(FileHandlerRegistry(handlers=[FakeHandler(fail=True)]))

    with pytest.raises(ValueError, match="parse failed"):
        handle(spec, lambda progress: None)

    assert source.exists()
    assert not cache.exists()
