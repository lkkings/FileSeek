from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.application.handlers.document import DocumentHandler
from fileseek.features.tasks.domain.entities import Task, TaskStage
from fileseek.features.tasks.domain.ports import (
    ClassifierLabelSnapshot,
    DocumentChunk,
    ParsedDocument,
)
from fileseek.infrastructure.classifier.base import ClassificationScore
from fileseek.shared.domain.file_types import FileCategory, FileType


class FakeParser:
    def parse_and_chunk(self, path: Path) -> ParsedDocument:
        _ = path
        return ParsedDocument(
            chunks=(DocumentChunk(text="content"),),
            page_count=1,
        )


class FakeEmbedding:
    def embed_text(self, texts: list[str]) -> list[list[float]]:
        _ = texts
        return [[0.1]]


class FakeVectorIndex:
    def add_batch(self, ids: list[str], vectors: list[list[float]]) -> None:
        _ = ids, vectors


class FakeClassifier:
    def classify_document(
        self,
        vectors: list[list[float]],
    ) -> list[ClassificationScore]:
        _ = vectors
        return [ClassificationScore(label="旧标签", score=1.0)]


class FakeClassifierProvider:
    def __init__(self) -> None:
        self.snapshots: list[ClassifierLabelSnapshot] = []

    def get_classifier(self, snapshot: ClassifierLabelSnapshot) -> FakeClassifier:
        self.snapshots.append(snapshot)
        return FakeClassifier()


class FakeProgress:
    def report(self, progress: int, stage: TaskStage) -> None:
        _ = progress, stage


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
    )

    handler.process(task, FakeProgress())

    assert file.tags == ["旧标签"]
    assert provider.snapshots == [snapshot]
