from __future__ import annotations

import logging

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
    DocumentParserPort,
    ProgressReporter,
)
from fileseek.infrastructure.classifier import ClassifierProvider
from fileseek.infrastructure.embedding import EmbeddingPort
from fileseek.shared.domain.file_types import FileType

logger = logging.getLogger(__name__)


class DocumentHandler(FileHandler):
    """文档文件处理器。"""

    def __init__(
        self,
        document_parser: DocumentParserPort,
        embedding_service: EmbeddingPort,
        classifier: ClassifierProvider,
        batch_size: int,
    ) -> None:
        self._document_parser = document_parser
        self._embedding_service = embedding_service
        self._classifier = classifier
        self._batch_size = batch_size

    def supports(self, file_type: FileType) -> bool:
        """判断是否支持当前文件类型。"""
        return file_type.is_document and file_type.is_support

    def compute(
        self,
        spec: TaskSpec,
        progress: ProgressReporter,
    ) -> TaskResult:
        """解析文档、向量化并分类。"""
        path = self.temp_path(spec)
        # ==================================================
        # 1. 提取文档内容
        # ==================================================
        progress.report(
            TaskStage.EXTRACTED,
            completed_count=0,
            total_count=1,
        )
        content = self._document_parser.parse_and_chunk(path)
        progress.report(
            TaskStage.EXTRACTED,
            completed_count=1,
            total_count=1,
        )
        # ==================================================
        # 2. 文档向量化
        # ==================================================
        total = len(content.chunks)
        if not content.chunks:
            logger.info(
                "文档没有可索引内容: path=%s",
                spec.file_path,
            )
            return TaskResult.empty()
        progress.report(
            TaskStage.ENCODED,
            completed_count=0,
            total_count=total,
        )
        embeddings: list[list[float]] = []
        for start in range(0, total, self._batch_size):
            chunks = content.chunks[start : start + self._batch_size]
            embeddings.extend(self._embedding_service.embed_text([chunk.text for chunk in chunks]))
            progress.report(
                TaskStage.ENCODED,
                completed_count=start + len(chunks),
                total_count=total,
            )
        progress.report(
            TaskStage.ENCODED,
            completed_count=total,
            total_count=total,
        )
        # ==================================================
        # 3. 文档分类
        # ==================================================
        progress.report(
            TaskStage.CLASSIFY,
            completed_count=0,
            total_count=1,
        )
        classifier = self._classifier.get_classifier(
            ClassifierLabelSnapshot.from_metadata(spec.metadata)
        )
        tags = tuple(score.label for score in classifier.classify_document(embeddings))
        progress.report(
            TaskStage.CLASSIFY,
            completed_count=1,
            total_count=1,
        )
        return TaskResult(
            chunks=tuple(
                ChunkPayload(
                    metadata={
                        "text": chunk.text,
                        "page_number": chunk.page_number,
                        "line_number": chunk.line_number,
                        "chunk_index": chunk.chunk_index,
                    }
                )
                for chunk in content.chunks
            ),
            vectors=as_vector_array(embeddings),
            tags=tags,
            index_batch_size=self._batch_size,
        )
