"""服务关闭时两个模型子进程都被收掉，不留下占内存的子进程。"""

from __future__ import annotations

import multiprocessing
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.search.query_worker_targets import fake_query_worker
from tests.tasks.worker_targets import fake_task_worker

from fileseek.bootstrap import lifespan as lifespan_module
from fileseek.bootstrap.container import Container
from fileseek.config.settings import Settings
from fileseek.features.search.infrastructure.query_worker import QueryEmbeddingClient
from fileseek.features.tasks.infrastructure import worker as task_worker_module
from fileseek.shared.infrastructure.worker import WorkerHandle


class _Paths:
    def __init__(self, root: Path) -> None:
        self.connection_file = root / "connection.json"

    def ensure_directories(self) -> None:
        pass


class _TaskRepo:
    async def list_all(self, status, page, size):
        return [], 0

    async def claim_next_queued(self):
        return None


class _FakeScheduler:
    def __init__(self) -> None:
        self.events: list[str] = []

    def start(self) -> None:
        self.events.append("scheduler-start")

    async def release_stranded(self) -> int:
        return 0

    async def shutdown(self, timeout: float) -> list[object]:
        _ = timeout
        self.events.append("scheduler-stop")
        return []


class _FakeFolderSourceWatcher:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def start(self) -> None:
        self.events.append("watcher-start")

    async def stop(self, timeout: float | None = None) -> None:
        _ = timeout
        self.events.append("watcher-stop")


@pytest.mark.asyncio
async def test_shutdown_leaves_no_model_subprocesses(tmp_path: Path, monkeypatch) -> None:
    async def _noop() -> None:
        return None

    monkeypatch.setattr(lifespan_module, "init_db", _noop)
    monkeypatch.setattr(lifespan_module, "close_db", _noop)
    monkeypatch.setattr(
        lifespan_module.AppPaths, "resolve", classmethod(lambda cls: _Paths(tmp_path))
    )
    # 导入 worker 换成不加载模型的假实现，其余装配走真实的 build_task_scheduler。
    monkeypatch.setattr(task_worker_module, "run_task_worker", fake_task_worker)
    monkeypatch.setattr("fileseek.bootstrap.container.run_task_worker", fake_task_worker)
    monkeypatch.setattr("fileseek.bootstrap.container.TaskRepositoryImpl", _TaskRepo)

    settings = Settings(lib_root=tmp_path, vector_db_path=tmp_path / "vectors")
    query_client = QueryEmbeddingClient(
        WorkerHandle("test-query-worker", fake_query_worker, {"idle_timeout": 0})
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            container=Container(settings=settings),
            dependencies={"query_embedding_client": query_client},
            publish_connection=False,
        )
    )

    async with lifespan_module.lifespan(app):  # type: ignore[arg-type]
        scheduler = app.state.container.scheduler
        assert scheduler is not None
        # 两个子进程都拉起来
        scheduler.compute.handle.ensure_started()
        assert query_client.embed_text("hi") == [[2.0, 0.0]]
        assert len(multiprocessing.active_children()) == 2

    assert multiprocessing.active_children() == []
    assert not query_client.handle.is_alive()


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_folder_source_watcher(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def _noop() -> None:
        return None

    monkeypatch.setattr(lifespan_module, "init_db", _noop)
    monkeypatch.setattr(lifespan_module, "close_db", _noop)
    monkeypatch.setattr(
        lifespan_module.AppPaths, "resolve", classmethod(lambda cls: _Paths(tmp_path))
    )
    scheduler = _FakeScheduler()
    watcher = _FakeFolderSourceWatcher()
    monkeypatch.setattr(
        lifespan_module,
        "build_task_scheduler",
        lambda _settings: scheduler,
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            container=Container(settings=Settings(lib_root=tmp_path)),
            dependencies={"folder_source_watcher_service": watcher},
            publish_connection=False,
        )
    )

    async with lifespan_module.lifespan(app):  # type: ignore[arg-type]
        assert app.state.container.folder_source_watcher is watcher

    assert scheduler.events == ["scheduler-start", "scheduler-stop"]
    assert watcher.events == ["watcher-start", "watcher-stop"]
