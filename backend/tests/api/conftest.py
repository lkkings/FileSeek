"""API 测试的装配与隔离。

每个测试拿到一个全新的临时库：自己的 SQLite 文件、自己的库根目录、自己的配置目录。
三件事必须一起做，否则测试之间会串味：

1. `get_settings` 有 lru_cache，不清掉的话第二个测试还拿着第一个测试的临时路径。
2. 数据库连接是模块级单例（`infrastructure/database/connection.py` 的 `_db_connection`），
   不 close 的话它还连着上一个测试已经删掉的文件。
3. `AppPaths.resolve()` 指向真实的用户配置目录。测试必须把它挪开——否则
   lifespan 会往真机的 `connection.json` 上写，而桌面端正轮询那个文件。

另外一处被替换成假实现，为了不产生真实副作用：

- 检索的 embedder / 向量库：真货会去下载 jina-clip-v2 权重，并开一个 Chroma 客户端。
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fileseek.bootstrap.app import create_app
from fileseek.bootstrap.auth import TOKEN_HEADER
from fileseek.config import paths as paths_module
from fileseek.config.paths import AppPaths
from fileseek.config.settings import Settings, get_settings
from fileseek.features.search.interfaces.http.dependencies import (
    get_embedder,
    get_vector_store,
)
from fileseek.features.tasks.domain.ports import VectorHit, VectorSearchFilters
from fileseek.infrastructure.database.models import (
    FileModel,
    FolderModel,
    RecentAccessModel,
    RecycleItemModel,
    TaskModel,
)
from fileseek.shared.domain.file_types import FileType

TEST_TOKEN = "test-token"  # noqa: S105 - 测试用固定值，不是真凭据
API = "/api/v1"


class FakeEmbedder:
    """固定向量的 embedder，不加载任何模型。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed_text(self, texts: str) -> list[float]:
        self.calls.append(texts)
        return [0.1, 0.2, 0.3]


class FakeVectorStore:
    """记录调用并返回预置结果的向量库，实现 VectorIndexPort.search 契约。"""

    def __init__(self) -> None:
        self.results: list[VectorHit] = []
        self.calls: list[tuple[list[float], list[FileType], int, VectorSearchFilters | None]] = []

    def search(
        self,
        query_vector: list[float],
        file_types: list[FileType],
        limit: int,
        filters: VectorSearchFilters | None = None,
    ) -> list[VectorHit]:
        self.calls.append((query_vector, file_types, limit, filters))
        return self.results


@pytest.fixture
def lib_root(tmp_path: Path) -> Path:
    """本次测试的文件库根目录。"""
    root = tmp_path / "library"
    root.mkdir()
    return root


@pytest.fixture
def test_settings(tmp_path: Path, lib_root: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """指向临时路径的配置，并清掉 get_settings 的缓存。"""
    settings = Settings(
        lib_root=lib_root,
        db_path=tmp_path / "metadata.db",
        vector_db_path=tmp_path / "vectors",
    )

    get_settings.cache_clear()

    # 只 patch 仍由基础设施自行读取配置的模块；HTTP interfaces 从 app.state 获取配置。
    monkeypatch.setattr("fileseek.config.settings.get_settings", lambda: settings)
    monkeypatch.setattr(
        "fileseek.infrastructure.database.connection.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "fileseek.features.tasks.infrastructure.file_processor.vector.providers.get_settings",
        lambda: settings,
    )

    yield settings

    get_settings.cache_clear()


@pytest.fixture
def isolated_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把 AppPaths 指向临时目录，别碰真机的 connection.json。"""
    config_dir = tmp_path / "config"
    monkeypatch.setattr(
        paths_module.AppPaths,
        "resolve",
        classmethod(lambda cls: AppPaths(config_dir)),
    )
    return config_dir


class FakeScheduler:
    """不跑任何真实处理的调度器替身。

    调度器没有"禁用"开关（关掉它入库的文件会永远停在 queued，那个故障从界面上看不出
    原因），所以 API 测试靠替换它来避开真实处理流程——真货会加载 jina-clip-v2 权重、
    起 OCR 和视频采样、真的移动文件。
    """

    def __init__(self) -> None:
        self.started = False

    @property
    def is_running(self) -> bool:
        return self.started

    @property
    def active_count(self) -> int:
        return 0

    def start(self) -> None:
        self.started = True

    async def release_stranded(self) -> tuple[str, ...]:
        return ()

    async def shutdown(self, timeout: float) -> tuple[str, ...]:  # noqa: ARG002
        self.started = False
        return ()


@pytest.fixture(autouse=True)
def fake_scheduler(monkeypatch: pytest.MonkeyPatch) -> FakeScheduler:
    """默认替换掉真实调度器。

    autouse：每个 API 测试都需要它，漏掉一个就会在那个测试里真的去加载模型。
    要验调度器本身启停的用例自己再覆盖一次（见 test_lifespan_scheduler.py）。
    """
    scheduler = FakeScheduler()
    monkeypatch.setattr(
        "fileseek.bootstrap.lifespan.build_task_scheduler",
        lambda _settings: scheduler,
    )
    return scheduler


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def fake_vector_store() -> FakeVectorStore:
    return FakeVectorStore()


@pytest.fixture
def app(
    test_settings: Settings,
    isolated_config_dir: Path,
    fake_embedder: FakeEmbedder,
    fake_vector_store: FakeVectorStore,
) -> Iterator[FastAPI]:
    """装好的应用，依赖已替换成不产生副作用的假实现。"""
    application = create_app(
        port=None,
        publish_connection=False,
        auth_token=TEST_TOKEN,
        settings=test_settings,
    )

    application.dependency_overrides[get_embedder] = lambda: fake_embedder
    application.dependency_overrides[get_vector_store] = lambda: fake_vector_store

    yield application

    application.dependency_overrides.clear()
    # lifespan 的 shutdown 钩子里已经 close_db() 过一次；Tortoise 的连接是进程级
    # 单例，多关一次是安全的，这里兜底防止某个测试绕开了 lifespan。


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """带 token 的客户端，覆盖大多数测试的需要。

    lifespan 在 `with` 语句进入时启动、退出时关闭——`init_db`/`close_db` 因此都在
    `test_client.portal` 持有的事件循环上跑。往库里塞种子数据必须复用同一个 portal
    （见 `seed` fixture），否则 Tortoise 的连接会绑在另一个事件循环上而找不到表。
    """
    with TestClient(app) as test_client:
        test_client.headers.update({TOKEN_HEADER: TEST_TOKEN})
        yield test_client


@pytest.fixture
def anon_client(app: FastAPI) -> Iterator[TestClient]:
    """不带 token 的客户端，用于鉴权测试。"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seed(client: TestClient) -> Any:
    """往库里塞数据的小工具。

    走真实的 Tortoise 模型（表已由 lifespan 的 `init_db` 建好），而不是 mock 仓储：
    API 测试要验的正是路由到 ORM 这一整条链路。

    Tortoise 的连接绑定在 `client` 进入 `with` 语句时启动的那个事件循环上（lifespan
    在其中跑了 `init_db`）。这里的写入必须经 `client.portal.call` 派发到同一个循环，
    否则会在另一个循环上找一个从没 `init_db` 过的连接。
    """

    class Seeder:
        def __init__(self, portal: Any) -> None:
            self.portal = portal

        def _create(self, model: Any, **fields: Any) -> None:
            """在 portal 的事件循环上创建一行。

            `BlockingPortal.call` 只收位置参数，所以关键字得先用 partial 绑进去。
            """
            self.portal.call(partial(model.create, **fields))

        def folder(
            self,
            folder_id: str = "f_1",
            name: str = "文档",
            icon_type: str = "icon-doc",
            description: str = "",
            modified: str = "2026-01-01T00:00:00+00:00",
            file_count: int = 0,
        ) -> str:
            self._create(
                FolderModel,
                id=folder_id,
                name=name,
                icon_type=icon_type,
                description=description,
                modified=modified,
                file_count=file_count,
            )
            return folder_id

        def file(
            self,
            file_id: str = "file_1",
            name: str = "report.pdf",
            media_type: str = "document",
            size: int = 1024,
            modified: str = "2026-01-02T00:00:00+00:00",
            parent_folder: str | None = None,
            path: str | None = None,
            import_source: str = "local",
            accessible: bool = True,
        ) -> str:
            self._create(
                FileModel,
                id=file_id,
                name=name,
                file_type=media_type,
                size=size,
                modified=modified,
                parent_folder_id=parent_folder,
                path=path or f"/seeded/{file_id}-{name}",
            )
            return file_id

        def recycle_item(
            self,
            item_id: str = "r_1",
            original_file_id: str = "file_1",
            original_name: str = "report.pdf",
            original_parent_folder: str | None = None,
            original_path: str = "/seeded/report.pdf",
            deleted_at: str = "2026-01-03T00:00:00+00:00",
            media_type: str = "document",
            size: int = 1024,
        ) -> str:
            self._create(
                RecycleItemModel,
                id=item_id,
                original_file_id=original_file_id,
                original_name=original_name,
                original_parent_folder=original_parent_folder,
                original_path=original_path,
                deleted_at=deleted_at,
                file_type=media_type,
                size=size,
            )
            return item_id

        def task(
            self,
            task_id: str = "t_1",
            source_path: str = "/seeded/a.pdf",
            status: str = "queued",
            progress: int = 0,
            stage: str | None = None,
            completed_stages: str = "[]",
            priority: int = 1,
            error_message: str | None = None,
            created_at: str = "2026-01-01T00:00:00+00:00",
            updated_at: str = "2026-01-01T00:00:00+00:00",
        ) -> str:
            self._create(
                TaskModel,
                id=task_id,
                source_path=source_path,
                status=status,
                progress=progress,
                stage=stage,
                completed_stages=completed_stages,
                priority=priority,
                error_message=error_message,
                created_at=created_at,
                updated_at=updated_at,
            )
            return task_id

        def recent_access(
            self,
            file_id: str = "file_1",
            accessed_at: str = "2026-01-04T00:00:00+00:00",
        ) -> None:
            self._create(
                RecentAccessModel,
                file_id=file_id,
                accessed_at=accessed_at,
            )

    assert client.portal is not None  # noqa: S101 - with 语句内 TestClient 保证已设置
    return Seeder(client.portal)
