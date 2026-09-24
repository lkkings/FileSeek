"""组装根：把跨请求存活的协作者装到一起。

请求作用域的依赖由各 feature 的 `interfaces/http/dependencies.py` 经 FastAPI `Depends`
自行解析，这里只负责后台任务调度器——它有自己的生命周期，由 lifespan 启停。

向量存储和嵌入服务这两个进程内单例放在 `infrastructure/vector/providers.py`，不在
这里：组装根要 import 各 feature 的路由，feature 的 dependencies 再 import 回组装根
就成了环。检索和调度器都从那个模块取同一个实例。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fileseek.config.settings import Settings
from fileseek.features.tasks.application.scheduler import TaskScheduler
from fileseek.features.tasks.application.processor import TaskProcessor
from fileseek.features.tasks.infrastructure.repositories import TaskRepositoryImpl
from fileseek.features.tasks.infrastructure.file_processor import DocumentParser
from fileseek.features.tasks.infrastructure.file_processor import OCRService
from fileseek.features.tasks.infrastructure.file_processor import VideoSampler
from fileseek.features.tasks.infrastructure.vector_store import (
    get_vector_store,
)
from fileseek.features.tasks.infrastructure.embedding import (
    get_embedding_service
)

logger = logging.getLogger(__name__)


def build_task_scheduler(settings: Settings) -> TaskScheduler:
    """装配后台任务调度器。

    调度器持有自己的仓储实例：它在后台线程里跑，和请求作用域的连接互不相干。
    """
    processor = TaskProcessor(
        document_parser=DocumentParser(),
        ocr_service=OCRService(),
        video_sampler=VideoSampler(
            sample_every_n_frames=settings.video_sample_every_n_frames,
            hash_threshold=settings.video_perceptual_hash_threshold,
        ),
        embedding_service=get_embedding_service(),
        vector_index=get_vector_store()
    )

    return TaskScheduler(
        task_repo=TaskRepositoryImpl(),
        processor=processor,
        poll_interval=settings.task_poll_interval,
        max_workers=settings.task_max_workers,
    )


@dataclass
class Container:
    """服务运行期持有的长生命周期协作者。

    放在 `app.state.container` 上，lifespan 负责启停，路由需要时从 request 取。
    """

    settings: Settings
    scheduler: TaskScheduler | None = None
