from __future__ import annotations

from functools import lru_cache

from fileseek.config.settings import get_settings
from fileseek.infrastructure.classifier.base import ClassifierPort
from fileseek.infrastructure.classifier.jina_clip_v2 import JinaClipV2Classifier
from fileseek.infrastructure.embedding import get_embedding_service


@lru_cache
def get_classifier() -> ClassifierPort:
    settings = get_settings()
    return ClassifierFactory.create(
        provider=settings.classifier_provider,
        embedding=get_embedding_service(),
        document_labels=settings.classifier_document_labels,
        video_labels=settings.classifier_video_labels,
        image_labels=settings.classifier_image_labels,
        text_similarity_threshold=settings.classifier_text_similarity_threshold,
        image_similarity_threshold=settings.classifier_image_similarity_threshold,
        video_similarity_threshold=settings.classifier_video_similarity_threshold,
        max_labels=settings.classifier_max_labels,
    )


class ClassifierFactory:
    _DEFAULT_PROVIDER = "jina-clip-v2"

    @classmethod
    def create(
        cls,
        provider: str = _DEFAULT_PROVIDER,
        *,
        embedding: object,
        document_labels: list[str],
        video_labels: list[str],
        image_labels: list[str],
        text_similarity_threshold: float = 0.3,
        image_similarity_threshold: float = 0.3,
        video_similarity_threshold: float = 0.3,
        max_labels: int = 5,
    ) -> ClassifierPort:
        if provider.strip().lower() == "jina-clip-v2":
            return JinaClipV2Classifier(
                embedding=embedding,
                document_labels=document_labels,
                video_labels=video_labels,
                image_labels=image_labels,
                text_similarity_threshold=text_similarity_threshold,
                image_similarity_threshold=image_similarity_threshold,
                video_similarity_threshold=video_similarity_threshold,
                max_labels=max_labels,
            )
        raise ValueError(f"不支持的 Classifier provider: {provider}")
