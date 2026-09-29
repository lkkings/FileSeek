from __future__ import annotations

from datetime import UTC, datetime

from fileseek.features.library.domain.entities import File
from fileseek.features.tasks.application.handlers.image import ImageHandler
from fileseek.features.tasks.domain.entities import Task, TaskStage
from fileseek.infrastructure.classifier.base import ClassificationScore
from fileseek.shared.domain.file_types import FileCategory, FileType


class _FakeOCR:
    def extract_text(self, path) -> str:
        return "sunset"


class _FakeEmbedding:
    def embed_image(self, image: bytes) -> list[list[float]]:
        return [[0.1]]

    def embed_text(self, texts: str | list[str]) -> list[list[float]]:
        return [[0.2]]


class _FakeVectorIndex:
    def __init__(self) -> None:
        self.batches: list[tuple[list[str], list[list[float]]]] = []

    def add_batch(self, ids, vectors) -> None:
        self.batches.append((list(ids), list(vectors)))


class _FakeClassifier:
    def get_classifier(self, snapshot):
        return self

    def classify_image(self, vector: list[float]) -> list[ClassificationScore]:
        return [ClassificationScore(label="sunset", score=0.9)]


class _FakeProgress:
    def __init__(self) -> None:
        self.reports: list[tuple[TaskStage, int, int]] = []

    def report(
        self,
        stage: TaskStage,
        completed_count: int,
        total_count: int,
    ) -> None:
        self.reports.append((stage, completed_count, total_count))


def test_image_handler_preserves_ocr_feature_indexing(tmp_path) -> None:
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"fake image bytes")
    file = File(
        id="file-1",
        name="image.png",
        file_type=FileType.PNG,
        category=FileCategory.IMAGE,
        size=15,
        modified=datetime(2026, 9, 29, tzinfo=UTC),
        path=str(image_path),
    )
    metadata = {
        "temp_path": str(image_path),
        "classifier_labels": {
            "document": ["report"],
            "image": ["sunset"],
            "video": ["clip"],
        },
        "classifier_label_version": "test-version",
    }
    task = Task(id="task-1", file=file, metadata=metadata)
    vector_index = _FakeVectorIndex()
    progress = _FakeProgress()
    handler = ImageHandler(
        ocr_service=_FakeOCR(),
        embedding_service=_FakeEmbedding(),
        vector_index=vector_index,
        classifier=_FakeClassifier(),
    )

    handler.process(task, progress)

    assert [chunk.metadata["feature_type"] for chunk in file.chunks] == [
        "image",
        "ocr",
    ]
    assert file.chunks[1].metadata["text"] == "sunset"
    assert vector_index.batches == [
        (
            ["file-1_0", "file-1_1"],
            [[0.1], [0.2]],
        ),
    ]
    assert progress.reports == [
        (TaskStage.EXTRACTED, 0, 1),
        (TaskStage.EXTRACTED, 1, 1),
        (TaskStage.ENCODED, 0, 2),
        (TaskStage.ENCODED, 2, 2),
        (TaskStage.CLASSIFY, 0, 1),
        (TaskStage.CLASSIFY, 1, 1),
        (TaskStage.INDEXED, 0, 2),
        (TaskStage.INDEXED, 2, 2),
    ]
