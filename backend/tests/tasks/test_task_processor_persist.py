from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.application.compute import ChunkPayload, TaskResult
from fileseek.features.tasks.application.processor import TaskProcessor
from fileseek.features.tasks.domain.entities import Task, TaskStage
from fileseek.shared.domain.file_types import FileCategory, FileType


class _FakeVectorIndex:
    def __init__(self) -> None:
        self.batches: list[tuple[list[str], list[list[float]]]] = []
        self.deleted: list[str] = []

    def add_batch(self, ids, vectors) -> None:
        self.batches.append((list(ids), list(vectors)))

    def delete_batch(self, ids) -> None:
        self.deleted.extend(ids)


class _FakeProgress:
    def __init__(self) -> None:
        self.reports: list[tuple[TaskStage, int, int]] = []

    def report(self, stage: TaskStage, completed_count: int, total_count: int) -> None:
        self.reports.append((stage, completed_count, total_count))


def _task() -> Task:
    file = File(
        id="file-1",
        name="doc.txt",
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path="/source/doc.txt",
        storage_id="local",
    )
    return Task(id="task-1", file=file, metadata={"temp_path": "cache/x", "k": "v"})


def test_build_spec_copies_plain_fields() -> None:
    task = _task()

    spec = TaskProcessor.build_spec(task)

    assert (spec.task_id, spec.file_id, spec.file_type, spec.file_path) == (
        "task-1",
        "file-1",
        FileType.TXT,
        "/source/doc.txt",
    )
    assert spec.metadata == {"temp_path": "cache/x", "k": "v"}
    # 是副本：子进程侧的修改不应影响服务进程的任务
    assert spec.metadata is not task.metadata


def test_persist_writes_batches_chunks_tags_and_progress() -> None:
    task = _task()
    index = _FakeVectorIndex()
    progress = _FakeProgress()
    result = TaskResult(
        chunks=tuple(ChunkPayload(metadata={"chunk_index": i}) for i in range(5)),
        vectors=np.arange(5, dtype=np.float32).reshape(5, 1),
        tags=("report",),
        index_batch_size=2,
    )

    TaskProcessor(vector_index=index).persist(task, result, progress)

    assert [ids for ids, _ in index.batches] == [
        ["file-1_0", "file-1_1"],
        ["file-1_2", "file-1_3"],
        ["file-1_4"],
    ]
    assert index.batches[2][1] == [[4.0]]
    assert [chunk.id for chunk in task.file.chunks] == [f"file-1_{i}" for i in range(5)]
    assert [chunk.metadata for chunk in task.file.chunks] == [{"chunk_index": i} for i in range(5)]
    assert task.file.tags == ["report"]
    assert progress.reports == [
        (TaskStage.INDEXED, 0, 5),
        (TaskStage.INDEXED, 2, 5),
        (TaskStage.INDEXED, 4, 5),
        (TaskStage.INDEXED, 5, 5),
        (TaskStage.INDEXED, 5, 5),
    ]


def test_persist_empty_result_writes_nothing() -> None:
    task = _task()
    index = _FakeVectorIndex()
    progress = _FakeProgress()

    TaskProcessor(vector_index=index).persist(task, TaskResult.empty(), progress)

    assert index.batches == []
    assert task.file.chunks == []
    assert progress.reports == []


def test_result_rejects_mismatched_chunks_and_vectors() -> None:
    with pytest.raises(ValueError, match="数量不一致"):
        TaskResult(
            chunks=(ChunkPayload(metadata={}),),
            vectors=np.zeros((2, 3), dtype=np.float32),
        )


def test_cleanup_deletes_written_chunk_ids() -> None:
    task = _task()
    index = _FakeVectorIndex()
    processor = TaskProcessor(vector_index=index)
    processor.persist(
        task,
        TaskResult(
            chunks=(ChunkPayload(metadata={}), ChunkPayload(metadata={})),
            vectors=np.zeros((2, 1), dtype=np.float32),
            index_batch_size=2,
        ),
        _FakeProgress(),
    )

    processor.cleanup(task)

    assert index.deleted == ["file-1_0", "file-1_1"]
