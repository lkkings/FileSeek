from __future__ import annotations

from fileseek.features.tasks.application.compute import (
    ChunkPayload,
    TaskResult,
    TaskSpec,
    as_vector_array,
)
from fileseek.features.tasks.application.handlers.base import FileHandler
from fileseek.features.tasks.domain.entities import TaskStage
from fileseek.features.tasks.domain.ports import (
    ClassifierLabelSnapshot,
    ProgressReporter,
)
from fileseek.infrastructure.classifier import ClassifierProvider
from fileseek.infrastructure.embedding import EmbeddingPort
from fileseek.infrastructure.ocr import ImageContent, OCRPort
from fileseek.shared.domain.file_types import FileType


class ImageHandler(FileHandler):
    """图片文件处理器。"""

    def __init__(
        self,
        ocr_service: OCRPort,
        embedding_service: EmbeddingPort,
        classifier: ClassifierProvider,
    ) -> None:
        self._ocr_service = ocr_service
        self._embedding_service = embedding_service
        self._classifier = classifier

    def supports(
        self,
        file_type: FileType,
    ) -> bool:
        return file_type.is_image and file_type.is_support

    def compute(
        self,
        spec: TaskSpec,
        progress: ProgressReporter,
    ) -> TaskResult:
        """处理图片。

        流程：

            OCR
             ↓
            图片 Embedding
             ↓
            OCR 文本 Embedding
             ↓
            图片分类
        """
        path = self.temp_path(spec)
        # --------------------------------------------------
        # 1. OCR
        # --------------------------------------------------
        progress.report(
            stage=TaskStage.EXTRACTED,
            completed_count=0,
            total_count=1,
        )
        ocr_text = self._ocr_service.extract_text(path)
        content = ImageContent(
            image=path,
            ocr_text=ocr_text,
        )
        progress.report(
            stage=TaskStage.EXTRACTED,
            completed_count=1,
            total_count=1,
        )
        # --------------------------------------------------
        # 2. 图片 Embedding
        # --------------------------------------------------
        total_count = 1 + int(bool(content.ocr_text))
        progress.report(
            stage=TaskStage.ENCODED,
            completed_count=0,
            total_count=total_count,
        )
        image_bytes = path.read_bytes()
        image_embeddings = self._embedding_service.embed_image(image_bytes)
        image_embedding = image_embeddings[0]
        features: list[dict[str, object]] = [
            {
                "feature_type": "image",
            }
        ]
        embeddings: list[list[float]] = [image_embedding]
        # --------------------------------------------------
        # 3. OCR 文本 Embedding
        # --------------------------------------------------
        if content.ocr_text:
            text_embedding = self._embedding_service.embed_text(content.ocr_text)[0]
            features.append(
                {
                    "feature_type": "ocr",
                    "text": content.ocr_text,
                }
            )
            embeddings.append(text_embedding)
        progress.report(
            stage=TaskStage.ENCODED,
            completed_count=total_count,
            total_count=total_count,
        )
        # --------------------------------------------------
        # 4. 图片分类
        # --------------------------------------------------
        progress.report(
            stage=TaskStage.CLASSIFY,
            completed_count=0,
            total_count=1,
        )
        classifier = self._classifier.get_classifier(
            ClassifierLabelSnapshot.from_metadata(spec.metadata)
        )
        scores = classifier.classify_image(embeddings[0])
        tags = tuple(score.label for score in scores)
        progress.report(
            stage=TaskStage.CLASSIFY,
            completed_count=1,
            total_count=1,
        )
        # 图片和 OCR 文本一次写入：原实现就是单批 add_batch。
        return TaskResult(
            chunks=tuple(ChunkPayload(metadata=feature) for feature in features),
            vectors=as_vector_array(embeddings),
            tags=tags,
            index_batch_size=len(embeddings),
        )
