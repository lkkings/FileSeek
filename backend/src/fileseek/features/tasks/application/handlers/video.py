from __future__ import annotations

from pathlib import Path

from fileseek.features.library.domain.entities import FileChunk
from fileseek.features.tasks.domain.entities import Task,TaskStage
from fileseek.infrastructure.embedding import EmbeddingPort
from fileseek.infrastructure.classifier import ClassifierPort
from fileseek.infrastructure.vector_store import (
    VectorIndexPort,
)
from fileseek.shared.domain.file_types import FileType
from fileseek.features.tasks.domain.ports import (
    VideoSamplerPort,
)

from fileseek.features.tasks.application.handlers.base import FileHandler
from fileseek.features.tasks.domain.ports import (
    ProgressReporter,
)


class VideoHandler(FileHandler):
    """视频处理器。"""

    def __init__(
        self,
        video_sampler: VideoSamplerPort,
        embedding_service: EmbeddingPort,
        vector_index: VectorIndexPort,
        classifier: ClassifierPort | None = None,
    ) -> None:
        self._video_sampler = video_sampler
        self._embedding_service = embedding_service
        self._vector_index = vector_index
        self._classifier = classifier

    def supports(
        self,
        file_type: FileType,
    ) -> bool:
        return file_type.is_video

    def process(
        self,
        task: Task,
        progress: ProgressReporter,
    ) -> None:
        path = Path(task.metadata["temp_path"])
        # -------------------------
        # 提取关键帧
        # -------------------------
        progress.report(
            0,
            TaskStage.EXTRACTED,
        )
        keyframes = (
            self._video_sampler.extract_keyframes(
                path
            )
        )
        progress.report(
            100,
            TaskStage.EXTRACTED,
        )
        if not keyframes:
            return []
        # -------------------------
        # embedding
        # -------------------------
        progress.report(0,TaskStage.ENCODED)
        indexed_keyframes = []
        embeddings = []
        total = len(keyframes)
        for index, keyframe in enumerate(
            keyframes,
            start=1,
        ):
            embedding = (
                self._embedding_service
                .embed_image(
                    keyframe.frame.data
                )[0]
            )
            embeddings.append(
                embedding
            )
            indexed_keyframes.append(
                {
                    "start_time": keyframe.start_time,
                    "end_time": keyframe.end_time,
                }
            )
            progress.report(
                index * 100 // total,
                TaskStage.ENCODED,
            )
        progress.report(
            100,
            TaskStage.ENCODED,
        )
        # -------------------------
        # 分类
        # -------------------------
        progress.report(
            0,
            TaskStage.CLASSIFY,
        )
        scores = self._classifier.classify_video(
            embeddings
        )
        tags = [
            score.label
            for score in scores
        ]
        task.add_file_tags(tags)
        progress.report(
            100,
            TaskStage.CLASSIFY,
        )
        # -------------------------
        # 建立索引
        # -------------------------
        progress.report(
            0,
            TaskStage.INDEXED,
        )
        ids = [f"{task.file.id}_{i}" for i in range(len(embeddings))]
        self._vector_index.add_batch(ids,vectors=embeddings)
        progress.report(
            100,
            TaskStage.INDEXED,
        )
        # -------------------------
        # 更新文件块状态
        # -------------------------
        file_chunks = [
            FileChunk(
                id=id,
                file_id=task.file.id,
                metadata=indexed_keyframe
            )
            for id, indexed_keyframe in zip(
                ids,
                indexed_keyframes,
                strict=True,
            )
        ]
        task.add_file_chunks(file_chunks)