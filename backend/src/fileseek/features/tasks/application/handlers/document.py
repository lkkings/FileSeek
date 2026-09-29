from __future__ import annotations

import logging
from pathlib import Path

from fileseek.features.library.domain.entities import FileChunk
from fileseek.features.tasks.application.handlers.base import FileHandler
from fileseek.features.tasks.domain.entities import Task, TaskStage
from fileseek.features.tasks.domain.ports import (
    ClassifierLabelSnapshot,
    DocumentParserPort,
    ProgressReporter,
)
from fileseek.infrastructure.classifier import ClassifierProvider
from fileseek.infrastructure.embedding import EmbeddingPort
from fileseek.infrastructure.vector_store import (
    VectorIndexPort,
)
from fileseek.shared.domain.file_types import FileType

logger = logging.getLogger(__name__)

class DocumentHandler(FileHandler):
    """文档文件处理器。"""

    def __init__(
        self,
        document_parser: DocumentParserPort,
        embedding_service: EmbeddingPort,
        vector_index: VectorIndexPort,
        classifier: ClassifierProvider,
        batch_size: int,
    ) -> None:
        self._document_parser = document_parser
        self._embedding_service = embedding_service
        self._vector_index = vector_index
        self._classifier = classifier
        self._batch_size = batch_size

    def supports(self, file_type: FileType) -> bool:
        """判断是否支持当前文件类型。"""
        return file_type.is_document and file_type.is_support

    def process(
        self,
        task: Task,
        progress: ProgressReporter,
    ) -> None:
        """处理文档并返回分类标签。"""
        metadata = task.metadata
        if metadata is None:
            raise ValueError("任务缺少元数据")
        temp_path = metadata.get("temp_path")
        if not isinstance(temp_path, str):
            raise TypeError("任务临时文件路径必须是字符串")
        path = Path(temp_path)
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
                task.file.path,
            )
            return
        progress.report(
            TaskStage.ENCODED,
            completed_count=0,
            total_count=total,
        )
        embeddings: list[list[float]] = []
        for start in range(0, total, self._batch_size):
            chunks = content.chunks[start : start + self._batch_size]
            embeddings.extend(
                self._embedding_service.embed_text(
                    [chunk.text for chunk in chunks]
                )
            )
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
            ClassifierLabelSnapshot.from_metadata(task.metadata)
        )
        tags = [
            score.label
            for score in classifier.classify_document(embeddings)
        ]
        task.add_file_tags(tags)
        progress.report(
            TaskStage.CLASSIFY,
            completed_count=1,
            total_count=1,
        )
        # ==================================================
        # 4. 建立索引
        # ==================================================
        progress.report(
            TaskStage.INDEXED,
            completed_count=0,
            total_count=total,
        )
        total = len(embeddings)
        for start in range(0, total, self._batch_size):
            vectors = embeddings[start : start + self._batch_size]
            ids = [
                f"{task.file.id}_{start + offset}"
                for offset in range(len(vectors))
            ]
            self._vector_index.add_batch(ids, vectors)
            task.add_file_chunks(
                [
                    FileChunk(
                        id=id,
                        file_id=task.file.id,
                        metadata={
                            "text": chunk.text,
                            "page_number": chunk.page_number,
                            "line_number": chunk.line_number,
                            "chunk_index": chunk.chunk_index,
                        }
                    )
                    for id, chunk in zip(
                        ids,
                        content.chunks[start : start + self._batch_size],
                        strict=True,
                    )
                ]
            )
            progress.report(
                TaskStage.INDEXED,
                completed_count=start + len(vectors),
                total_count=total,
            )
        progress.report(
            TaskStage.INDEXED,
            completed_count=total,
            total_count=total,
        )
        return
