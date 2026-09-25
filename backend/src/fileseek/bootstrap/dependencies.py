"""Composition-root construction for HTTP application dependencies."""

from __future__ import annotations

from typing import Any

from fileseek.config.settings import Settings
from fileseek.features.library.application.use_cases import (
    AddFileUseCase,
    CreateFolderUseCase,
    DeleteFileUseCase,
    DeleteFolderUseCase,
    GetFileUseCase,
    ListFilesUseCase,
    ListFoldersUseCase,
    UpdateFolderUseCase,
)
from fileseek.features.library.infrastructure.repositories import (
    FileRepositoryImpl,
    FolderRepositoryImpl,
)
from fileseek.features.recent.application.use_cases import (
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
from fileseek.features.settings.application.use_cases.get_settings import GetSettingsUseCase
from fileseek.features.settings.application.use_cases.test_nas_connection import (
    TestNASConnectionUseCase,
)
from fileseek.features.settings.application.use_cases.update_settings import (
    UpdateSettingsUseCase,
)
from fileseek.features.settings.infrastructure.repositories import TortoiseSettingsRepository
from fileseek.features.tasks.application.manager import DefaultTaskManager
from fileseek.features.tasks.application.use_cases import (
    GetTaskUseCase,
    ListTasksUseCase,
    RetryTaskUseCase,
)
from fileseek.features.tasks.infrastructure.embedding import get_embedding_service
from fileseek.features.tasks.infrastructure.repositories import TaskRepositoryImpl
from fileseek.features.tasks.infrastructure.vector_store import (
    get_vector_store,
)
from fileseek.shared.utils.cache import get_search_results_cache


def build_http_dependencies(settings: Settings) -> dict[str, Any]:
    file_repo = FileRepositoryImpl()
    folder_repo = FolderRepositoryImpl()
    recycle_repo = RecycleRepositoryImpl()
    recent_repo = RecentAccessRepositoryImpl()
    task_repo = TaskRepositoryImpl()
    # 与检索、调度器共用同一个 Chroma 客户端（get_vector_store 带 lru_cache）：
    # 同一个目录开两个客户端会互相打架。
    vector_store = get_vector_store()
    embedder = get_embedding_service()
    cache = get_search_results_cache()

    task_manager = DefaultTaskManager(task_repo)
    # settings 表还没有行时回退到配置里的库根目录，而不是报错。
    settings_repo = TortoiseSettingsRepository(str(settings.lib_root))
    return {
        # 文件夹管理
        "list_folders_use_case": ListFoldersUseCase(folder_repo),
        "create_folder_use_case": CreateFolderUseCase(folder_repo),
        "update_folder_use_case": UpdateFolderUseCase(folder_repo),
        "delete_folder_use_case": DeleteFolderUseCase(folder_repo),

        # 文件管理操作
        "add_file_use_case": AddFileUseCase(file_repo,folder_repo,task_manager),
        "delete_file_use_case": DeleteFileUseCase(file_repo),
        "list_files_use_case": ListFilesUseCase(file_repo, folder_repo),
        "get_file_use_case": GetFileUseCase(file_repo),
        "add_files2recycle_use_case": AddFiles2RecycleUseCase(
            file_repo, folder_repo, recycle_repo
        ),
        "list_recycle_items_use_case": ListRecycleItemsUseCase(recycle_repo),
        "restore_recycle_use_case": RestoreRecycleUseCase(
            recycle_repo, file_repo, folder_repo
        ),
        "delete_recycle_use_case": DeleteRecycleUseCase(
            recycle_repo, file_repo, vector_store
        ),
        "clear_recycle_bin_use_case": ClearRecycleBinUseCase(
            recycle_repo, file_repo, vector_store
        ),
        "list_recent_access_use_case": ListRecentAccessUseCase(recent_repo),
        "record_access_use_case": RecordAccessUseCase(recent_repo),

        # 文件搜索：元信息随向量落盘，检索不回库表，所以这里不再注入 file_repo。
        "search_files_use_case": SearchFilesUseCase(
            embedder, vector_store, file_repo, cache
        ),

        # 系统设置：这三个 provider 一直在等这几个键，但它们从没被注册过，
        # 所以 GET/POST /settings 和 NAS 测试此前都是 KeyError → 500。
        "get_settings_use_case": GetSettingsUseCase(settings_repo),
        "update_settings_use_case": UpdateSettingsUseCase(settings_repo),
        "test_nas_connection_use_case": TestNASConnectionUseCase(settings_repo),

        # 任务管理
        "get_task_use_case": GetTaskUseCase(task_manager),
        "list_tasks_use_case": ListTasksUseCase(task_repo),
        "retry_task_use_case": RetryTaskUseCase(task_manager),
    }
