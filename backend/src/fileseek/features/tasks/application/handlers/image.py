from __future__ import annotations

from pathlib import Path

from fileseek.features.library.domain.entities import FileChunk
from fileseek.features.tasks.domain.entities import Task,TaskStage
from fileseek.features.tasks.application.handlers.base import FileHandler
from fileseek.features.tasks.domain.ports import (
    ProgressReporter,
)
from fileseek.infrastructure.classifier import ClassifierProvider
from fileseek.features.tasks.domain.ports import ClassifierLabelSnapshot
from fileseek.infrastructure.embedding import EmbeddingPort
from fileseek.infrastructure.ocr import (
    ImageContent,
    OCRPort
)
from fileseek.infrastructure.vector_store import (
    VectorIndexPort,
)
from fileseek.shared.domain.file_types import FileType


class ImageHandler(FileHandler):
    """图片文件处理器。"""

    def __init__(
        self,
        ocr_service: OCRPort,
        embedding_service: EmbeddingPort,
        vector_index: VectorIndexPort,
        classifier: ClassifierProvider,
    ) -> None:
        self._ocr_service = ocr_service
        self._embedding_service = embedding_service
        self._vector_index = vector_index
        self._classifier = classifier

    def supports(
        self,
        file_type: FileType,
    ) -> bool:
        return file_type.is_image and file_type.is_support

    def process(
        self,
        task: Task,
        progress: ProgressReporter,
    ) -> None:
        """处理图片。

        流程：

            OCR
             ↓
            图片 Embedding
             ↓
            OCR 文本 Embedding
             ↓
            写入向量索引
             ↓
            图片分类
        """
        path = Path(task.metadata["temp_path"])
        # --------------------------------------------------
        # 1. OCR
        # --------------------------------------------------
        progress.report(
            stage=TaskStage.EXTRACTED,
            completed_count=0,
            total_count=1,
        )
        ocr_text = self._ocr_service.extract_text(
            path
        )
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
        image_embeddings = (
            self._embedding_service.embed_image(
                image_bytes
            )
        )
        image_embedding = image_embeddings[0]
        features: list[dict[str, object]] = [
            {
                "feature_type": "image",
            }
        ]
        embeddings: list[list[float]] = [
            image_embedding
        ]
        # --------------------------------------------------
        # 3. OCR 文本 Embedding
        # --------------------------------------------------
        if content.ocr_text:
            text_embedding = (
                self._embedding_service.embed_text(
                    content.ocr_text
                )[0]
            )
            features.append(
                {
                    "feature_type": "ocr",
                    "text": content.ocr_text,
                }
            )
            embeddings.append(
                text_embedding
            )
        progress.report(
            stage=TaskStage.ENCODED,
            completed_count=total_count,
            total_count=total_count,
        )
        # --------------------------------------------------
        # 4. 图片分类
        # --------------------------------------------------
        if not embeddings:
            return []
        progress.report(
            stage=TaskStage.CLASSIFY,
            completed_count=0,
            total_count=1,
        )
        classifier = self._classifier.get_classifier(
            ClassifierLabelSnapshot.from_metadata(task.metadata)
        )
        scores = classifier.classify_image(
            embeddings[0]
        )
        tags = [
            score.label
            for score in scores
        ]
        task.add_file_tags(tags)
        progress.report(
            stage=TaskStage.CLASSIFY,
            completed_count=1,
            total_count=1,
        )
        # ==================================================
        # 5. 建立索引
        # ==================================================
        progress.report(
            TaskStage.INDEXED,
            completed_count=0,
            total_count=len(embeddings),
        )
        ids = [f"{task.file.id}_{i}" for i in range(len(embeddings))]
        self._vector_index.add_batch(ids,vectors=embeddings)
        progress.report(
            TaskStage.INDEXED,
            completed_count=len(embeddings),
            total_count=len(embeddings),
        )
        # ==================================================
        # 6. 更新文件块状态
        # ==================================================
        file_chunks = [
            FileChunk(
                id=id,
                file_id=task.file.id,
                metadata=feature
            )
            for id, feature in zip(
                ids,
                features,
                strict=True,
            )
        ]
        task.add_file_chunks(file_chunks)
