from __future__ import annotations

import logging
from pathlib import Path

from fileseek.features.library.domain.entities import FileChunk
from fileseek.features.tasks.domain.entities import Task,TaskStage
from fileseek.infrastructure.classifier import ClassifierPort
from fileseek.infrastructure.embedding import EmbeddingPort
from fileseek.infrastructure.vector_store import (
    VectorIndexPort,
)
from fileseek.shared.domain.file_types import FileType
from fileseek.features.tasks.application.handlers.base import FileHandler
from fileseek.features.tasks.domain.ports import (
    DocumentParserPort,
    ParsedDocument,
    ProgressReporter
)
from fileseek.shared.domain.identifiers import generate_id


logger = logging.getLogger(__name__)


class DocumentHandler(FileHandler):
    """文档文件处理器。"""

    def __init__(
        self,
        document_parser: DocumentParserPort,
        embedding_service: EmbeddingPort,
        vector_index: VectorIndexPort,
        classifier: ClassifierPort,
    ) -> None:
        self._document_parser = document_parser
        self._embedding_service = embedding_service
        self._vector_index = vector_index
        self._classifier = classifier

    def supports(self, file_type: FileType) -> bool:
        """判断是否支持当前文件类型。"""
        return file_type.is_document

    def process(
        self,
        task: Task,
        progress: ProgressReporter,
    ) -> None:
        """处理文档并返回分类标签。"""
        path = Path(task.metadata["temp_path"])
        # ==================================================
        # 1. 提取文档内容
        # ==================================================
        progress.report(
            0,
            TaskStage.EXTRACTED,
        )
        content = self._document_parser.parse_and_chunk(path)
        progress.report(
            100,
            TaskStage.EXTRACTED,
        )
        # ==================================================
        # 2. 文档向量化
        # ==================================================
        progress.report(
            0,
            TaskStage.ENCODED,
        )
        if not content.chunks:
            logger.info(
                "文档没有可索引内容: path=%s",
                task.file.path,
            )
            return []
        texts = [
            chunk.text
            for chunk in content.chunks
        ]
        embeddings = self._embedding_service.embed_text(
            texts
        )
        progress.report(
            100,
            TaskStage.ENCODED,
        )
        # ==================================================
        # 3. 文档分类
        # ==================================================
        progress.report(
            0,
            TaskStage.CLASSIFY,
        )
        tags = self.classify(embeddings)
        task.add_file_tags(tags)
        progress.report(
            100,
            TaskStage.CLASSIFY,
        )
        # ==================================================
        # 4. 建立索引
        # ==================================================
        progress.report(
            0,
            TaskStage.INDEXED,
        )
        ids = [f"{task.file.id}_{i}" for i in range(len(embeddings))]
        self._vector_index.add_batch(ids,embeddings)
        progress.report(
            100,
            TaskStage.INDEXED,
        )

        # ==================================================
        # 5. 更新文件块状态
        # ==================================================
        file_chunks = [
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
                content.chunks,
                strict=True,
            )
        ]
        task.add_file_chunks(file_chunks)