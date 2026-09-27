from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ClassificationScore:
    label: str
    score: float


class ClassifierPort(Protocol):
    def __init__(
        self,
        document_labels: list[str],
        video_labels: list[str],
        image_labels: list[str],
    ) -> None: ...

    def classify_image(self, vector: list[float]) -> list[ClassificationScore]: ...

    def classify_video(self, vectors: list[list[float]]) -> list[ClassificationScore]: ...

    def classify_document(self, vectors: list[list[float]]) -> list[ClassificationScore]: ...
