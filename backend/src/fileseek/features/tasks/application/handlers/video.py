from __future__ import annotations

from pathlib import Path

from fileseek.features.library.domain.entities import FileChunk
from fileseek.features.tasks.application.handlers.base import FileHandler
from fileseek.features.tasks.domain.entities import Task, TaskStage
from fileseek.features.tasks.domain.ports import (
    ClassifierLabelSnapshot,
    ProgressReporter,
    VideoSamplerPort,
)
from fileseek.infrastructure.classifier import ClassifierProvider
from fileseek.infrastructure.embedding import EmbeddingPort
from fileseek.infrastructure.vector_store import (
    VectorIndexPort,
)
from fileseek.shared.domain.file_types import FileType


class VideoHandler(FileHandler):
    """视频处理器。"""

    def __init__(
        self,
        video_sampler: VideoSamplerPort,
        embedding_service: EmbeddingPort,
        vector_index: VectorIndexPort,
        batch_size: int,
        classifier: ClassifierProvider | None = None,
    ) -> None:
        self._video_sampler = video_sampler
        self._embedding_service = embedding_service
        self._vector_index = vector_index
        self._classifier = classifier
        self._batch_size = batch_size

    def supports(
        self,
        file_type: FileType,
    ) -> bool:
        return file_type.is_video and file_type.is_support

    def process(
        self,
        task: Task,
        progress: ProgressReporter,
    ) -> None:
        metadata = task.metadata
        if metadata is None:
            raise ValueError("任务缺少元数据")
        temp_path = metadata.get("temp_path")
        if not isinstance(temp_path, str):
            raise TypeError("任务临时文件路径必须是字符串")
        path = Path(temp_path)
        # -------------------------
        # 提取关键帧
        # -------------------------
        progress.report(
            TaskStage.EXTRACTED,
            completed_count=0,
            total_count=1,
        )
        keyframes = (
            self._video_sampler.extract_keyframes(
                path
            )
        )
        progress.report(
            TaskStage.EXTRACTED,
            completed_count=1,
            total_count=1,
        )
        if not keyframes:
            return
        # -------------------------
        # embedding
        # -------------------------
        total = len(keyframes)
        progress.report(
            TaskStage.ENCODED,
            completed_count=0,
            total_count=total,
        )
        indexed_keyframes: list[dict[str, object]] = []
        embeddings: list[list[float]] = []
        for start in range(0, total, self._batch_size):
            batch = keyframes[start : start + self._batch_size]
            embeddings.extend(
                self._embedding_service.embed_image(
                    [keyframe.frame.data for keyframe in batch]
                )
            )
            indexed_keyframes.extend(
                {
                    "start_time": keyframe.start_time,
                    "end_time": keyframe.end_time,
                }
                for keyframe in batch
            )
            progress.report(
                TaskStage.ENCODED,
                completed_count=start + len(batch),
                total_count=total,
            )
        progress.report(
            TaskStage.ENCODED,
            completed_count=total,
            total_count=total,
        )
        # -------------------------
        # 分类
        # -------------------------
        progress.report(
            TaskStage.CLASSIFY,
            completed_count=0,
            total_count=1,
        )
        if self._classifier is None:
            return
        classifier = self._classifier.get_classifier(
            ClassifierLabelSnapshot.from_metadata(task.metadata)
        )
        scores = classifier.classify_video(
            embeddings
        )
        tags = [
            score.label
            for score in scores
        ]
        task.add_file_tags(tags)
        progress.report(
            TaskStage.CLASSIFY,
            completed_count=1,
            total_count=1,
        )
        # -------------------------
        # 建立索引
        # -------------------------
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
            self._vector_index.add_batch(
                ids,
                vectors=vectors,
            )
            task.add_file_chunks(
                [
                    FileChunk(
                        id=id,
                        file_id=task.file.id,
                        metadata=indexed_keyframe,
                    )
                    for id, indexed_keyframe in zip(
                        ids,
                        indexed_keyframes[start : start + self._batch_size],
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
