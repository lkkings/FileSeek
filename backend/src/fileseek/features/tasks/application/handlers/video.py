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
    VideoSamplerPort,
)
from fileseek.infrastructure.classifier import ClassifierProvider
from fileseek.infrastructure.embedding import EmbeddingPort
from fileseek.shared.domain.file_types import FileType


class VideoHandler(FileHandler):
    """视频处理器。"""

    def __init__(
        self,
        video_sampler: VideoSamplerPort,
        embedding_service: EmbeddingPort,
        batch_size: int,
        classifier: ClassifierProvider | None = None,
    ) -> None:
        self._video_sampler = video_sampler
        self._embedding_service = embedding_service
        self._classifier = classifier
        self._batch_size = batch_size

    def supports(
        self,
        file_type: FileType,
    ) -> bool:
        return file_type.is_video and file_type.is_support

    def compute(
        self,
        spec: TaskSpec,
        progress: ProgressReporter,
    ) -> TaskResult:
        path = self.temp_path(spec)
        # -------------------------
        # 提取关键帧
        # -------------------------
        progress.report(
            TaskStage.EXTRACTED,
            completed_count=0,
            total_count=1,
        )
        keyframes = self._video_sampler.extract_keyframes(path)
        progress.report(
            TaskStage.EXTRACTED,
            completed_count=1,
            total_count=1,
        )
        if not keyframes:
            return TaskResult.empty()
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
                self._embedding_service.embed_image([keyframe.frame.data for keyframe in batch])
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
        tags: tuple[str, ...] = ()
        if self._classifier is not None:
            classifier = self._classifier.get_classifier(
                ClassifierLabelSnapshot.from_metadata(spec.metadata)
            )
            scores = classifier.classify_video(embeddings)
            tags = tuple(score.label for score in scores)
        progress.report(
            TaskStage.CLASSIFY,
            completed_count=1,
            total_count=1,
        )
        return TaskResult(
            chunks=tuple(ChunkPayload(metadata=keyframe) for keyframe in indexed_keyframes),
            vectors=as_vector_array(embeddings),
            tags=tags,
            index_batch_size=self._batch_size,
        )
