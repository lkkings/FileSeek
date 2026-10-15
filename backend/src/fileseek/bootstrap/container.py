"""应用组装根。

负责组装跨请求、跨任务生命周期存活的协作者。

依赖方向：

    bootstrap
        ↓
    features / infrastructure

后台任务：

    TaskScheduler ──TaskSpec/TaskResult──> 导入模型子进程
        ↓                                   FileHandlerRegistry
    TaskProcessor（写向量库）                 DocumentHandler / ImageHandler / VideoHandler
                                            embedding / OCR / classifier

服务进程这一侧不构建任何模型：handler 及其依赖由子进程自己组装（见
`features/tasks/infrastructure/worker.py`）。

请求作用域的依赖由各 Feature 的
`interfaces/http/dependencies.py` 通过 FastAPI Depends 自行解析。

这里不负责请求级依赖。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fileseek.config.settings import Settings
from fileseek.features.library.infrastructure.repositories import (
    FileChunkRepositoryImpl,
    FileRepositoryImpl,
)
from fileseek.features.library.infrastructure.watcher import (
    FolderSourceWatcherService,
)
from fileseek.features.tasks.application.cancellation import (
    get_task_cancellation_registry,
)
from fileseek.features.tasks.application.processor import (
    TaskProcessor,
)
from fileseek.features.tasks.application.scheduler import (
    TaskScheduler,
)
from fileseek.features.tasks.infrastructure.repositories import (
    TaskRepositoryImpl,
)
from fileseek.features.tasks.infrastructure.worker import (
    TASK_WORKER_NAME,
    TaskWorkerClient,
    build_task_worker_config,
    run_task_worker,
)
from fileseek.infrastructure.vector_store import (
    get_vector_store,
)
from fileseek.shared.infrastructure.worker import WorkerHandle
from fileseek.shared.utils.cache import (
    get_cache_service,
)

logger = logging.getLogger(__name__)


def build_task_scheduler(
    settings: Settings,
) -> TaskScheduler:
    """组装后台任务调度器。

    计算交给导入模型子进程（按需启动、空闲退出、崩溃后重启），
    TaskProcessor 只负责把结果写进向量库，
    TaskScheduler 只负责任务调度。
    """
    vector_index = get_vector_store()
    cache = get_cache_service()
    cancellation_registry = get_task_cancellation_registry()

    compute = TaskWorkerClient(
        WorkerHandle(
            TASK_WORKER_NAME,
            run_task_worker,
            build_task_worker_config(settings),
        )
    )

    return TaskScheduler(
        task_repo=TaskRepositoryImpl(),
        file_repo=FileRepositoryImpl(),
        file_chunk_repo=FileChunkRepositoryImpl(),
        processor=TaskProcessor(vector_index=vector_index),
        compute=compute,
        poll_interval=settings.task_poll_interval,
        cache=cache,
        cancellation_registry=cancellation_registry,
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
    folder_source_watcher: FolderSourceWatcherService | None = None
