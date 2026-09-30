"""Composition-root construction for HTTP application dependencies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fileseek.config.settings import Settings
from fileseek.features.library.application.use_cases import (
    AddFileUseCase,
    BatchImportSessionManager,
    CheckFileAvailabilityUseCase,
    CreateFolderUseCase,
    DeleteFolderUseCase,
    GetFileSourceUseCase,
    GetFileThumbnailUseCase,
    GetFileUseCase,
    ListFoldersUseCase,
    ListTagsUseCase,
    MoveFilesUseCase,
    StartBatchImportUseCase,
    UpdateFolderUseCase,
)
from fileseek.features.library.infrastructure.repositories import (
    FileRepositoryImpl,
    FolderRepositoryImpl,
)
from fileseek.features.recent.application.use_cases import (
    DeleteRecentAccessUseCase,
    ListRecentAccessUseCase,
    RecordAccessUseCase,
)
from fileseek.features.recent.infrastructure.repositories import RecentAccessRepositoryImpl
from fileseek.features.recycle.application.use_cases import (
    AddFiles2RecycleUseCase,
    ClearRecycleBinUseCase,
    DeleteRecycleUseCase,
    ListRecycleItemsUseCase,
    RestoreRecycleUseCase,
)
from fileseek.features.recycle.infrastructure.repositories import RecycleRepositoryImpl
from fileseek.features.search.application.use_cases import SearchFilesUseCase
from fileseek.features.settings.application.use_cases import (
    CreateStorageLocationUseCase,
    DeleteStorageLocationUseCase,
    GetClassifierLabelsUseCase,
    ListStorageDirectoryUseCase,
    ListStorageLocationsUseCase,
    ReplaceClassifierLabelsUseCase,
    TestStorageConnectionUseCase,
    UpdateStorageLocationUseCase,
)
from fileseek.features.settings.infrastructure import (
    FilesystemStorageDirectoryBrowser,
    StorageSourceResolver,
    TortoiseClassifierLabelProvider,
    TortoiseClassifierLabelRepository,
    TortoiseStorageLocationRepository,
)
from fileseek.features.tasks.application.cancellation import (
    get_task_cancellation_registry,
)
from fileseek.features.tasks.application.manager import DefaultTaskManager
from fileseek.features.tasks.application.use_cases import (
    CancelTaskUseCase,
    DeleteTaskUseCase,
    ListTasksUseCase,
    RetryTaskUseCase,
)
from fileseek.features.tasks.infrastructure.repositories import TaskRepositoryImpl
from fileseek.features.search.infrastructure.query_worker import (
    QUERY_WORKER_NAME,
    QueryEmbeddingClient,
    build_query_worker_config,
    run_query_worker,
)
from fileseek.infrastructure.thumbnail_cache import ThumbnailCache
from fileseek.infrastructure.thumbnails import ThumbnailGenerator
from fileseek.infrastructure.vector_store import (
    get_vector_store,
)
from fileseek.shared.infrastructure.worker import WorkerHandle
from fileseek.shared.utils.cache import get_cache_service


def build_http_dependencies(settings: Settings) -> dict[str, Any]:
    file_repo = FileRepositoryImpl()
    folder_repo = FolderRepositoryImpl()
    recycle_repo = RecycleRepositoryImpl()
    recent_repo = RecentAccessRepositoryImpl()
    task_repo = TaskRepositoryImpl()
    # 与检索、调度器共用同一个 Chroma 客户端（get_vector_store 带 lru_cache）：
    # 同一个目录开两个客户端会互相打架。
    vector_store = get_vector_store()
    # 查询向量化在独立的查询模型子进程里做（和导入进程互不影响、空闲自动退出），
    # 服务进程本身不加载模型。子进程按需启动：这里只是建句柄，不会立刻拉起。
    query_embedder = QueryEmbeddingClient(
        WorkerHandle(
            QUERY_WORKER_NAME,
            run_query_worker,
            build_query_worker_config(settings),
        )
    )
    cache = get_cache_service()

    task_manager = DefaultTaskManager(
        task_repo,
        get_task_cancellation_registry(),
    )
    thumbnail_dir = settings.temp_dir
    if thumbnail_dir is None:
        thumbnail_dir = Path.cwd() / ".fileseek-thumbnails"
    thumbnail_cache = ThumbnailCache(thumbnail_dir / "thumbnails")
    storage_location_repo = TortoiseStorageLocationRepository()
    classifier_label_repo = TortoiseClassifierLabelRepository()
    add_file_use_case = AddFileUseCase(
        file_repo,
        folder_repo,
        task_manager,
        StorageSourceResolver(storage_location_repo),
        TortoiseClassifierLabelProvider(classifier_label_repo),
    )
    batch_import_session_manager = BatchImportSessionManager(
        add_file_use_case,
    )
    # settings 表还没有行时回退到配置里的库根目录，而不是报错。

    return {
        # 文件夹管理
        "list_folders_use_case": ListFoldersUseCase(folder_repo),
        "list_tags_use_case": ListTagsUseCase(file_repo),
        "create_folder_use_case": CreateFolderUseCase(folder_repo),
        "update_folder_use_case": UpdateFolderUseCase(folder_repo),
        "delete_folder_use_case": DeleteFolderUseCase(folder_repo),

        # 文件管理
        "add_file_use_case": add_file_use_case,
        "batch_import_session_manager": batch_import_session_manager,
        "start_batch_import_use_case": StartBatchImportUseCase(
            folder_repo,
            batch_import_session_manager,
        ),
        "get_file_use_case": GetFileUseCase(file_repo),
        "get_file_source_use_case": GetFileSourceUseCase(
            file_repo,
            StorageSourceResolver(storage_location_repo),
        ),
        "get_file_thumbnail_use_case": GetFileThumbnailUseCase(
            file_repo,
            ThumbnailGenerator(),
            thumbnail_cache,
            StorageSourceResolver(storage_location_repo),
        ),
        "move_files_use_case": MoveFilesUseCase(file_repo, folder_repo, cache),
        "check_file_availability_use_case": CheckFileAvailabilityUseCase(
            file_repo,
            StorageSourceResolver(storage_location_repo),
        ),

        # 回收站管理
        "add_files2recycle_use_case": AddFiles2RecycleUseCase(
            file_repo,
            recycle_repo,
            cache,
            StorageSourceResolver(storage_location_repo),
        ),
        "list_recycle_items_use_case": ListRecycleItemsUseCase(recycle_repo),
        "restore_recycle_use_case": RestoreRecycleUseCase(
            recycle_repo,
            file_repo,
            cache,
            StorageSourceResolver(storage_location_repo),
        ),
        "delete_recycle_use_case": DeleteRecycleUseCase(
            recycle_repo, file_repo, vector_store
        ),
        "clear_recycle_bin_use_case": ClearRecycleBinUseCase(
            recycle_repo, file_repo, vector_store
        ),
        "list_recent_access_use_case": ListRecentAccessUseCase(recent_repo, file_repo),
        "record_access_use_case": RecordAccessUseCase(recent_repo),
        "delete_recent_access_use_case": DeleteRecentAccessUseCase(recent_repo),

        # 文件搜索：元信息随向量落盘，检索不回库表，所以这里不再注入 file_repo。
        "search_files_use_case": SearchFilesUseCase(
            query_embedder, vector_store, file_repo, cache
        ),
        "query_embedding_client": query_embedder,

        # 系统设置
        "get_classifier_labels_use_case": GetClassifierLabelsUseCase(
            classifier_label_repo
        ),
        "replace_classifier_labels_use_case": ReplaceClassifierLabelsUseCase(
            classifier_label_repo
        ),
        "list_storage_locations_use_case": ListStorageLocationsUseCase(
            storage_location_repo
        ),
        "list_storage_directory_use_case": ListStorageDirectoryUseCase(
            storage_location_repo,
            FilesystemStorageDirectoryBrowser(),
        ),
        "create_storage_location_use_case": CreateStorageLocationUseCase(
            storage_location_repo
        ),
        "update_storage_location_use_case": UpdateStorageLocationUseCase(
            storage_location_repo
        ),
        "delete_storage_location_use_case": DeleteStorageLocationUseCase(
            storage_location_repo,
        ),
        "test_storage_connection_use_case": TestStorageConnectionUseCase(
            storage_location_repo
        ),

        # 任务管理
        "list_tasks_use_case": ListTasksUseCase(task_repo),
        "retry_task_use_case": RetryTaskUseCase(task_manager),
        "cancel_task_use_case": CancelTaskUseCase(task_manager),
        "delete_task_use_case": DeleteTaskUseCase(task_manager),
    }
