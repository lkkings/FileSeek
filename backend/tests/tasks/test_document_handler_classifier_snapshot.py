from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.application.handlers.document import DocumentHandler
from fileseek.features.tasks.application.handlers.video import VideoHandler
from fileseek.features.tasks.domain.entities import Task, TaskStage
from fileseek.features.tasks.domain.ports import (
    ClassifierLabelSnapshot,
    DocumentChunk,
    ParsedDocument,
    VideoFrame,
    VideoKeyframe,
)
from fileseek.infrastructure.classifier.base import ClassificationScore
from fileseek.shared.domain.file_types import FileCategory, FileType


class FakeParser:
    def __init__(self, chunk_count: int = 1) -> None:
        self.chunk_count = chunk_count

    def parse_and_chunk(self, path: Path) -> ParsedDocument:
        _ = path
        return ParsedDocument(
            chunks=tuple(
                DocumentChunk(text=f"content-{index}", chunk_index=index)
                for index in range(self.chunk_count)
            ),
            page_count=1,
        )


class FakeEmbedding:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def embed_text(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return [[0.1] for _ in texts]


class FakeVectorIndex:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def add_batch(self, ids: list[str], vectors: list[list[float]]) -> None:
        self.batch_sizes.append(len(ids))


class FakeClassifier:
    def classify_document(
        self,
        vectors: list[list[float]],
    ) -> list[ClassificationScore]:
        _ = vectors
        return [ClassificationScore(label="旧标签", score=1.0)]


class FakeVideoSampler:
    def __init__(self, keyframe_count: int) -> None:
        self.keyframe_count = keyframe_count

    def extract_keyframes(self, path: Path) -> tuple[VideoKeyframe, ...]:
        _ = path
        return tuple(
            VideoKeyframe(
                start_time=float(index),
                end_time=float(index + 1),
                frame=VideoFrame(data=f"frame-{index}".encode()),
            )
            for index in range(self.keyframe_count)
        )


class FakeImageEmbedding:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def embed_image(self, images: list[bytes]) -> list[list[float]]:
        self.batch_sizes.append(len(images))
        return [[0.1] for _ in images]


class FakeVideoClassifier:
    def classify_video(
        self,
        vectors: list[list[float]],
    ) -> list[ClassificationScore]:
        _ = vectors
        return [ClassificationScore(label="旧标签", score=1.0)]


class FakeVideoClassifierProvider:
    def __init__(self) -> None:
        self.snapshots: list[ClassifierLabelSnapshot] = []

    def get_classifier(self, snapshot: ClassifierLabelSnapshot) -> FakeVideoClassifier:
        self.snapshots.append(snapshot)
        return FakeVideoClassifier()


class FakeClassifierProvider:
    def __init__(self) -> None:
        self.snapshots: list[ClassifierLabelSnapshot] = []

    def get_classifier(self, snapshot: ClassifierLabelSnapshot) -> FakeClassifier:
        self.snapshots.append(snapshot)
        return FakeClassifier()


class FakeProgress:
    def __init__(self) -> None:
        self.reports: list[tuple[TaskStage, int, int]] = []

    def report(
        self,
        stage: TaskStage,
        completed_count: int,
        total_count: int,
    ) -> None:
        self.reports.append((stage, completed_count, total_count))


def test_document_handler_uses_task_label_snapshot(tmp_path: Path) -> None:
    snapshot = ClassifierLabelSnapshot(
        document_labels=("旧标签",),
        image_labels=(),
        video_labels=(),
        version="old-version",
    )
    file = File(
        id="file-1",
        name="document.txt",
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path=str(tmp_path / "document.txt"),
        storage_id="local",
    )
    task = Task(
        id="task-1",
        file=file,
        metadata={
            "temp_path": str(tmp_path / "cache.txt"),
            **snapshot.as_metadata(),
        },
    )
    provider = FakeClassifierProvider()
    handler = DocumentHandler(
        document_parser=FakeParser(),
        embedding_service=FakeEmbedding(),
        vector_index=FakeVectorIndex(),
        classifier=provider,
        batch_size=4,
    )

    handler.process(task, FakeProgress())

    assert file.tags == ["旧标签"]
    assert provider.snapshots == [snapshot]


def test_document_handler_batches_processing_and_reports_progress(
    tmp_path: Path,
) -> None:
    file = File(
        id="file-1",
        name="document.txt",
        file_type=FileType.TXT,
        category=FileCategory.DOCUMENT,
        size=1,
        modified=datetime.now(UTC),
        path=str(tmp_path / "document.txt"),
        storage_id="local",
    )
    task = Task(
        id="task-1",
        file=file,
        metadata={
            "temp_path": str(tmp_path / "cache.txt"),
            **ClassifierLabelSnapshot(
                document_labels=("旧标签",),
                image_labels=(),
                video_labels=(),
                version="old-version",
            ).as_metadata(),
        },
    )
    embedding = FakeEmbedding()
    vector_index = FakeVectorIndex()
    progress = FakeProgress()
    handler = DocumentHandler(
        document_parser=FakeParser(chunk_count=9),
        embedding_service=embedding,
        vector_index=vector_index,
        classifier=FakeClassifierProvider(),
        batch_size=4,
    )

    handler.process(task, progress)

    assert embedding.batch_sizes == [4, 4, 1]
    assert vector_index.batch_sizes == [4, 4, 1]
    assert len(file.chunks) == 9
    assert [chunk.id for chunk in file.chunks] == [
        f"file-1_{index}" for index in range(9)
    ]
    encoded_counts = [
        (report[1], report[2])
        for report in progress.reports
        if report[0] is TaskStage.ENCODED
    ]
    indexed_counts = [
        (report[1], report[2])
        for report in progress.reports
        if report[0] is TaskStage.INDEXED
    ]
    assert encoded_counts == [(0, 9), (4, 9), (8, 9), (9, 9), (9, 9)]
    assert indexed_counts == [(0, 9), (4, 9), (8, 9), (9, 9), (9, 9)]


def test_video_handler_batches_processing_and_reports_progress(
    tmp_path: Path,
) -> None:
    file = File(
        id="file-1",
        name="video.mp4",
        file_type=FileType.MP4,
        category=FileCategory.VIDEO,
        size=1,
        modified=datetime.now(UTC),
        path=str(tmp_path / "video.mp4"),
        storage_id="local",
    )
    task = Task(
        id="task-1",
        file=file,
        metadata={
            "temp_path": str(tmp_path / "cache.mp4"),
            **ClassifierLabelSnapshot(
                document_labels=(),
                video_labels=("旧标签",),
                image_labels=(),
                version="old-version",
            ).as_metadata(),
        },
    )
    embedding = FakeImageEmbedding()
    vector_index = FakeVectorIndex()
    progress = FakeProgress()
    handler = VideoHandler(
        video_sampler=FakeVideoSampler(keyframe_count=9),
        embedding_service=embedding,
        vector_index=vector_index,
        batch_size=4,
        classifier=FakeVideoClassifierProvider(),
    )

    handler.process(task, progress)

    assert embedding.batch_sizes == [4, 4, 1]
    assert vector_index.batch_sizes == [4, 4, 1]
    assert len(file.chunks) == 9
    assert [chunk.id for chunk in file.chunks] == [
        f"file-1_{index}" for index in range(9)
    ]
    encoded_counts = [
        (report[1], report[2])
        for report in progress.reports
        if report[0] is TaskStage.ENCODED
    ]
    indexed_counts = [
        (report[1], report[2])
        for report in progress.reports
        if report[0] is TaskStage.INDEXED
    ]
    assert encoded_counts == [(0, 9), (4, 9), (8, 9), (9, 9), (9, 9)]
    assert indexed_counts == [(0, 9), (4, 9), (8, 9), (9, 9), (9, 9)]
