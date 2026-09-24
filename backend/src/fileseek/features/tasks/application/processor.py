"""任务内容处理应用服务。

负责协调：

    文件类型识别
        ↓
    内容抽取
        ↓
    内容编码
        ↓
    向量索引

处理器本身不修改 Task，也不负责任务持久化。
任务状态和进度由上层调度器负责保存。

进度上报属于派生信息，因此采用尽力而为策略：
进度队列异常不会导致实际的内容处理任务失败。
"""

from __future__ import annotations

import logging
import queue
from datetime import UTC, datetime
from pathlib import Path

from fileseek.features.tasks.domain.entities import (
    Task,
    TaskProgress,
    TaskStage,
)
from fileseek.features.tasks.domain.ports import (
    ParsedDocument,
    ImageContent,
    VideoKeyframe,
    DocumentParserPort,
    EmbeddingPort,
    IndexedFileMetadata,
    OCRPort,
    VectorIndexPort,
    VideoSamplerPort,
)
from fileseek.shared.domain.file_types import FileType
from fileseek.infrastructure.fs import VirtualPath
from fileseek.shared.utils.file_utils import detect_file_type

logger = logging.getLogger(__name__)


class TaskProcessor:
    """任务内容处理器。

    该类属于应用层，负责组织各个领域 Port 完成一次文件处理。

    它不负责：

    - 修改 Task 状态
    - 保存 Task
    - 管理数据库事务
    - 管理进度持久化
    """

    def __init__(
        self,
        document_parser: DocumentParserPort,
        ocr_service: OCRPort,
        video_sampler: VideoSamplerPort,
        embedding_service: EmbeddingPort,
        vector_index: VectorIndexPort
    ) -> None:
        self._document_parser = document_parser
        self._ocr_service = ocr_service
        self._video_sampler = video_sampler
        self._embedding_service = embedding_service
        self._vector_index = vector_index

    def process(
        self,
        task: Task,
        progress_queue: queue.Queue[TaskProgress] | None = None,
    ):
        """处理一个任务。

        阶段：

        25%  文件已移动
        50%  内容抽取完成
        75%  内容编码并写入索引
        100% 索引完成

        Args:
            task: 已经进入 PROCESSING 状态的任务。
            progress_queue: 可选的进度队列。

        不返回结果：阶段和进度都经 `progress_queue` 上报，任务状态的落库是调度器
        那一侧的事（见 `application/scheduler.py`）。
        """
        logger.info(
            "开始处理任务: task_id=%s, path=%s",
            task.id,
            task.source_path,
        )

        file_type = detect_file_type(task.source_path)

        content = self._extract_content(
            task.source_path,
            file_type,
        )


        self._report(
            progress_queue,
            progress=50,
            stage=TaskStage.EXTRACTED,
        )

        indexed_file = self._describe_file(task)

        self._encode_content(
            metadata=indexed_file,
            file_type=file_type,
            content=content,
        )

        self._report(
            progress_queue,
            progress=75,
            stage=TaskStage.ENCODED,
        )

        self._report(
            progress_queue,
            progress=100,
            stage=TaskStage.INDEXED,
        )

        logger.info(
            "任务处理完成: task_id=%s",
            task.id,
        )
        VirtualPath(task.source_path).delete()


    # ------------------------------------------------------------------
    # 内容抽取
    # ------------------------------------------------------------------

    def _extract_content(
        self,
        source_path: str,
        file_type: FileType,
    ) -> ParsedDocument | ImageContent | tuple[VideoKeyframe, ...]:
        """根据文件类型抽取结构化内容。"""
        path = Path(source_path)

        match file_type:
            case FileType.DOCUMENT:
                return self._extract_document(path)

            case FileType.IMAGE:
                return self._extract_image(path)

            case FileType.VIDEO:
                return self._extract_video(path)

            case _:
                raise ValueError(
                    f"不支持的文件类型: {file_type}"
                )

    def _extract_document(
        self,
        path: Path,
    ) -> ParsedDocument:
        """抽取并切分文档。"""
        return self._document_parser.parse_and_chunk(path)

    def _extract_image(
        self,
        path: Path,
    ) -> ImageContent:
        """抽取图片内容。

        图片同时保留：

        - 原始图片，用于图片特征 embedding
        - OCR 文本，用于文本 embedding
        """
        ocr_text = self._ocr_service.extract_text(path)

        return ImageContent(
            image=path,
            ocr_text=ocr_text or None,
        )


    def _extract_video(
        self,
        path: Path,
    ) -> tuple[VideoKeyframe, ...]:
        """提取视频关键帧。"""
        return self._video_sampler.extract_keyframes(path)

    # ------------------------------------------------------------------
    # 内容编码
    # ------------------------------------------------------------------

    def _encode_content(
        self,
        metadata: IndexedFileMetadata,
        file_type: FileType,
        content: ParsedDocument | ImageContent | tuple[VideoKeyframe, ...],
    ) -> None:
        """编码内容并写入向量索引。"""
        match file_type:
            case FileType.DOCUMENT:
                self._encode_document(
                    metadata,
                    self._expect_document(content),
                )

            case FileType.IMAGE:
                self._encode_image(
                    metadata,
                    self._expect_image(content),
                )

            case FileType.VIDEO:
                self._encode_video(
                    metadata,
                    self._expect_video(content),
                )

            case _:
                raise ValueError(
                    f"不支持的文件类型: {file_type}"
                )

    def _encode_document(
        self,
        metadata: IndexedFileMetadata,
        document: ParsedDocument,
    ) -> None:
        """编码文档切片。"""
        if not document.chunks:
            logger.info(
                "文档没有可索引内容: file_id=%s",
                metadata.file_id,
            )
            return

        texts = [
            chunk.text
            for chunk in document.chunks
        ]

        embeddings = self._embedding_service.embed_text(texts)

        indexed_chunks = [
            {
                "text": chunk.text,
                "page_number": chunk.page_number,
                "line_number": chunk.line_number,
                "chunk_index": chunk.chunk_index,
                "embedding": embedding,
            }
            for chunk, embedding in zip(
                document.chunks,
                embeddings,
                strict=True,
            )
        ]

        self._vector_index.add_document_vectors(
            metadata,
            indexed_chunks,
        )

    def _encode_image(
        self,
        metadata: IndexedFileMetadata,
        image: ImageContent,
    ) -> None:
        """同时编码图片特征和 OCR 文本。"""
        features: list[dict[str, object]] = []
        image_bytes = Path(image.image).read_bytes()
        # 图片特征向量。
        #
        # `embed_image` 永远返回一批（`list[list[float]]`），传一张也是 `[[...]]`，所以要取
        # 第 0 条。不取的话这里存进去的就比约定深一层，向量库那边再包一层成 `[[[...]]]`，
        # Chroma 报 "Expected embeddings to be a list of floats or ints ... got [[["。
        image_embedding = self._embedding_service.embed_image(
            image_bytes
        )[0]

        features.append(
            {
                "feature_type": "image",
                "embedding": image_embedding,
            }
        )

        # OCR 文本向量。同上，传单条字符串拿回来的也是一批，取第 0 条。
        if image.ocr_text:
            text_embedding = self._embedding_service.embed_text(
                image.ocr_text,
            )[0]

            features.append(
                {
                    "feature_type": "ocr",
                    "text": image.ocr_text,
                    "embedding": text_embedding,
                }
            )

        self._vector_index.add_image_vectors(
            metadata,
            features,
        )

    def _encode_video(
        self,
        metadata: IndexedFileMetadata,
        keyframes: tuple[VideoKeyframe, ...],
    ) -> None:
        """编码视频关键帧。"""
        if not keyframes:
            logger.info(
                "视频没有可索引关键帧: file_id=%s",
                metadata.file_id,
            )
            return

        indexed_keyframes = []

        for keyframe in keyframes:
            # 同上，一帧一帧编码，拿回来的还是一批，取第 0 条。
            embedding = self._embedding_service.embed_image(
                keyframe.frame.data,
            )[0]

            indexed_keyframes.append(
                {
                    "start_time": keyframe.start_time,
                    "end_time": keyframe.end_time,
                    "embedding": embedding,
                }
            )

        self._vector_index.add_video_vectors(
            metadata,
            indexed_keyframes,
        )

    # ------------------------------------------------------------------
    # 文件信息
    # ------------------------------------------------------------------

    @staticmethod
    def _describe_file(
        task: Task,
    ) -> IndexedFileMetadata:
        """获取写入向量索引的文件元数据。"""
        path = Path(task.source_path)

        size: int | None = None
        modified: str | None = None
        modified_ts: float | None = None
        accessible = False

        try:
            stat = path.stat()
        except OSError:
            logger.warning(
                "无法读取文件属性，元数据留空: %s",
                task.source_path,
            )
        else:
            size = stat.st_size
            modified_ts = stat.st_mtime
            modified = datetime.fromtimestamp(
                stat.st_mtime,
                tz=UTC,
            ).isoformat()
            accessible = True

        return IndexedFileMetadata(
            file_id=task.id,
            file_name=path.name,
            path=task.source_path,
            size=size,
            modified=modified,
            modified_ts=modified_ts,
            accessible=accessible,
        )
    # ------------------------------------------------------------------
    # 类型检查
    # ------------------------------------------------------------------

    @staticmethod
    def _expect_document(
        content: ParsedDocument
        | ImageContent
        | tuple[VideoKeyframe, ...],
    ) -> ParsedDocument:
        if not isinstance(content, ParsedDocument):
            raise TypeError(
                f"预期 ParsedDocument，实际得到 {type(content).__name__}"
            )

        return content

    @staticmethod
    def _expect_image(
        content: ParsedDocument
        | ImageContent
        | tuple[VideoKeyframe, ...],
    ) -> ImageContent:
        if not isinstance(content, ImageContent):
            raise TypeError(
                f"预期 ImageContent，实际得到 {type(content).__name__}"
            )

        return content

    @staticmethod
    def _expect_video(
        content: ParsedDocument
        | ImageContent
        | tuple[VideoKeyframe, ...],
    ) -> tuple[VideoKeyframe, ...]:
        if not isinstance(content, tuple):
            raise TypeError(
                f"预期 VideoKeyframe 元组，实际得到 {type(content).__name__}"
            )

        return content

    # ------------------------------------------------------------------
    # 进度
    # ------------------------------------------------------------------

    @staticmethod
    def _report(
        progress_queue: queue.Queue[TaskProgress] | None,
        progress: int,
        stage: TaskStage,
    ) -> None:
        """尽力上报任务进度。

        进度属于派生信息，无法上报不能影响核心处理流程。
        """
        if progress_queue is None:
            return

        try:
            progress_queue.put(
                TaskProgress(
                    progress=progress,
                    stage=stage,
                )
            )
        except Exception:
            logger.exception(
                "任务进度上报失败: stage=%s, progress=%s",
                stage.value,
                progress,
            )