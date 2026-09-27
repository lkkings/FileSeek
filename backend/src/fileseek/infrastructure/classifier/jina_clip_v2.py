from __future__ import annotations


from fileseek.infrastructure.embedding.base import (
    EmbeddingPort
)
from fileseek.infrastructure.classifier.base import (
    ClassificationScore,
    ClassifierPort,
)


class JinaClipV2Classifier(ClassifierPort):
    """Zero-shot label classifier using the shared Jina CLIP embedding space."""

    def __init__(
        self,
        embedding: EmbeddingPort,
        document_labels: list[str],
        video_labels: list[str],
        image_labels: list[str],
        text_similarity_threshold: float = 0.3,
        image_similarity_threshold: float = 0.3,
        video_similarity_threshold: float = 0.3,
        max_labels: int = 5,
    ) -> None:
        self._embedding = embedding
        self._thresholds = {
            "document": text_similarity_threshold,
            "image": image_similarity_threshold,
            "video": video_similarity_threshold,
        }
        self._max_labels = max_labels
        self._label_vectors = {
            "document": self._embed_labels(document_labels),
            "video": self._embed_labels(video_labels),
            "image": self._embed_labels(image_labels),
        }

    def classify_image(self, vector: list[float]) -> list[ClassificationScore]:
        return self._classify_vectors([vector], "image")

    def classify_video(self, vectors: list[list[float]]) -> list[ClassificationScore]:
        return self._classify_vectors(vectors, "video")

    def classify_document(self, vectors: list[list[float]]) -> list[ClassificationScore]:
        return self._classify_vectors(vectors, "document")

    def _embed_labels(self, labels: list[str]) -> list[tuple[str, list[float]]]:
        cleaned = [label.strip() for label in labels if label.strip()]
        if not cleaned:
            return []
        vectors = self._embedding.embed_text(cleaned)
        return list(zip(cleaned, vectors, strict=True))

    def _classify_vectors(
        self,
        vectors: list[list[float]],
        kind: str,
    ) -> list[ClassificationScore]:
        if not vectors:
            return []
        candidates = self._label_vectors[kind]
        scores = [
            ClassificationScore(
                label=label,
                score=sum(
                    _cosine_similarity(vector, label_vector)
                    for vector in vectors
                ) / len(vectors),
            )
            for label, label_vector in candidates
        ]
        scores = [
            item for item in scores if item.score >= self._thresholds[kind]
        ]
        return sorted(scores, key=lambda item: item.score, reverse=True)[: self._max_labels]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if not left_norm or not right_norm:
        return -1.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
