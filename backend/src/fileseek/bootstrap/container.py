"""应用组装根。

负责组装跨请求、跨任务生命周期存活的协作者。

依赖方向：

    bootstrap
        ↓
    features / infrastructure

后台任务：

    TaskScheduler
        ↓
    TaskProcessor
        ↓
    FileHandlerRegistry
        ↓
    DocumentHandler / ImageHandler / VideoHandler
        ↓
    各基础设施服务

请求作用域的依赖由各 Feature 的
`interfaces/http/dependencies.py` 通过 FastAPI Depends 自行解析。

这里不负责请求级依赖。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fileseek.config.settings import Settings

from fileseek.features.library.infrastructure.repositories import (
    FileRepositoryImpl,
    FileChunkRepositoryImpl
)

from fileseek.features.tasks.application.handlers import (
    DocumentHandler,
    FileHandlerRegistry,
    ImageHandler,
    VideoHandler,
)
from fileseek.features.tasks.application.processor import (
    TaskProcessor,
)
from fileseek.features.tasks.application.scheduler import (
    TaskScheduler,
)

from fileseek.features.tasks.infrastructure.file_processor import (
    DocumentParser,
    VideoSampler,
)
from fileseek.features.tasks.infrastructure.repositories import (
    TaskRepositoryImpl,
)

from fileseek.infrastructure.classifier import (
    get_classifier,
)
from fileseek.infrastructure.embedding import (
    get_embedding_service,
)
from fileseek.infrastructure.ocr import (
    get_ocr_service,
)
from fileseek.infrastructure.vector_store import (
    get_vector_store,
)

from fileseek.shared.utils.cache import (
    get_cache_service,
)

logger = logging.getLogger(__name__)


def build_task_scheduler(
    settings: Settings,
) -> TaskScheduler:
    """组装后台任务调度器。

    这里创建后台任务所需的完整依赖图。

    Handler 负责具体文件类型的处理逻辑，
    TaskProcessor 只负责调度 Handler，
    TaskScheduler 只负责任务调度。
    """

    # ==================================================
    # 基础设施
    # ==================================================

    embedding_service = get_embedding_service()
    vector_index = get_vector_store()
    classifier = get_classifier()
    ocr_service = get_ocr_service()
    cache = get_cache_service()

    # ==================================================
    # 文件处理基础服务
    # ==================================================

    document_parser = DocumentParser()

    video_sampler = VideoSampler(
        sample_every_n_frames=(
            settings.video_sample_every_n_frames
        ),
        hash_threshold=(
            settings.video_perceptual_hash_threshold
        ),
    )

    # ==================================================
    # File Handlers
    # ==================================================

    document_handler = DocumentHandler(
        document_parser=document_parser,
        embedding_service=embedding_service,
        vector_index=vector_index,
        classifier=classifier,
    )

    image_handler = ImageHandler(
        ocr_service=ocr_service,
        embedding_service=embedding_service,
        vector_index=vector_index,
        classifier=classifier,
    )

    video_handler = VideoHandler(
        video_sampler=video_sampler,
        embedding_service=embedding_service,
        vector_index=vector_index,
        classifier=classifier,
    )

    # ==================================================
    # Handler Registry
    # ==================================================

    handler_registry = FileHandlerRegistry(
        handlers=[
            document_handler,
            image_handler,
            video_handler,
        ]
    )

    # ==================================================
    # Task Processor
    # ==================================================

    processor = TaskProcessor(
        handler_registry=handler_registry,
        vector_index=vector_index,
    )

    # ==================================================
    # Repository
    # ==================================================

    file_repo = FileRepositoryImpl()
    file_chunk_repo = FileChunkRepositoryImpl()
    task_repo = TaskRepositoryImpl()

    # ==================================================
    # Task Scheduler
    # ==================================================

    return TaskScheduler(
        task_repo=task_repo,
        file_repo=file_repo,
        file_chunk_repo=file_chunk_repo,
        processor=processor,
        poll_interval=settings.task_poll_interval,
        max_workers=settings.task_max_workers,
        cache=cache,
    )


@dataclass
class Container:
    """应用运行期的长生命周期协作者。

    实例挂载到：

        app.state.container

    由应用 lifespan 负责创建和关闭。
    """

    settings: Settings
    scheduler: TaskScheduler | None = None