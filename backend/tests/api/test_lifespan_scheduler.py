"""调度器在生命周期里的启停用例。

调度器没有禁用开关：关掉它入库的文件会永远停在 queued，那个故障从界面上看不出原因。
所有 API 测试都把 `build_task_scheduler` 换成不做事的替身（conftest 里是 autouse 的），
真货会构造 embedding / OCR / 视频采样服务。这一支自带一个会记录启停调用的替身。

关闭路径上的两条容错分支也在这里：调度器关闭抛异常、数据库关闭抛异常，都不能让
lifespan 崩掉。关闭只有一次机会，抛出去会盖掉真正的退出原因，还会把连接文件留在
原地——客户端于是一直连一个没人监听的端口。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from fileseek.bootstrap.app import create_app
from fileseek.config.settings import Settings


class FakeScheduler:
    """记录启停调用的调度器替身。"""

    def __init__(self) -> None:
        self.started = False
        self.released_on_start = False
        self.shutdown_calls: list[float] = []
        self.shutdown_error: Exception | None = None
        self.stranded: tuple[str, ...] = ()

    @property
    def is_running(self) -> bool:
        return self.started

    @property
    def active_count(self) -> int:
        return 0

    def start(self) -> None:
        self.started = True

    async def release_stranded(self) -> tuple[str, ...]:
        """和真实的 `TaskScheduler.release_stranded` 一样是 async——它要 await 仓储。"""
        self.released_on_start = True
        return self.stranded

    async def shutdown(self, timeout: float) -> tuple[str, ...]:
        self.shutdown_calls.append(timeout)
        if self.shutdown_error is not None:
            raise self.shutdown_error
        self.started = False
        return ()


@pytest.fixture
def scheduler_settings(test_settings: Settings) -> Settings:
    """调度器没有开关，这个别名留着是为了让用例读起来明确在验调度器。"""
    return test_settings


@pytest.fixture
def fake_scheduler(monkeypatch: pytest.MonkeyPatch) -> FakeScheduler:
    """覆盖 conftest 里那个 autouse 的替身：这里要记录启停调用。"""
    scheduler = FakeScheduler()
    monkeypatch.setattr(
        "fileseek.bootstrap.lifespan.build_task_scheduler",
        lambda _settings: scheduler,
    )
    return scheduler


def test_scheduler_starts_and_stops_with_the_app(
    scheduler_settings: Settings,
    isolated_config_dir: Path,
    fake_scheduler: FakeScheduler,
) -> None:
    app = create_app(publish_connection=False, settings=scheduler_settings)

    with TestClient(app):
        assert fake_scheduler.started is True

    assert fake_scheduler.shutdown_calls == [scheduler_settings.task_drain_timeout]
    assert fake_scheduler.started is False


def test_startup_releases_tasks_stranded_by_a_crash(
    scheduler_settings: Settings,
    isolated_config_dir: Path,
    fake_scheduler: FakeScheduler,
) -> None:
    """上次运行崩溃留下的 processing 任务要被放回队列。

    没有这一步，那些任务谁也不会去取（claim_next_queued 只看 queued），界面上就是
    一堆永远停在"处理中"的文件。
    """
    fake_scheduler.stranded = ("t_1", "t_2")

    app = create_app(publish_connection=False, settings=scheduler_settings)

    with TestClient(app):
        assert fake_scheduler.released_on_start is True


def test_health_reports_scheduler_running(
    scheduler_settings: Settings,
    isolated_config_dir: Path,
    fake_scheduler: FakeScheduler,
) -> None:
    app = create_app(publish_connection=False, settings=scheduler_settings)

    with TestClient(app) as client:
        from tests.api.conftest import TEST_TOKEN

        from fileseek.bootstrap.auth import TOKEN_HEADER

        client.headers.update({TOKEN_HEADER: TEST_TOKEN})
        body = client.get("/health").json()

    assert body["data"]["scheduler_running"] is True


def test_shutdown_survives_scheduler_failure(
    scheduler_settings: Settings,
    isolated_config_dir: Path,
    fake_scheduler: FakeScheduler,
) -> None:
    """调度器关闭失败不能让 lifespan 崩，后面的清理还得继续。"""
    fake_scheduler.shutdown_error = RuntimeError("调度器炸了")
    app = create_app(port=8899, publish_connection=True, settings=scheduler_settings)
    connection_file = isolated_config_dir / "connection.json"

    with TestClient(app):
        assert connection_file.is_file()

    # 关键：尽管调度器抛了异常，连接文件仍然被撤掉了。
    assert not connection_file.exists()


def test_shutdown_survives_database_failure(
    scheduler_settings: Settings,
    isolated_config_dir: Path,
    fake_scheduler: FakeScheduler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """数据库关闭失败同样不能把关闭流程带崩。"""

    def boom() -> None:
        raise RuntimeError("库已经不在了")

    monkeypatch.setattr("fileseek.bootstrap.lifespan.close_db", boom)

    app = create_app(port=8899, publish_connection=True, settings=scheduler_settings)

    with TestClient(app):
        pass

    assert not (isolated_config_dir / "connection.json").exists()


def test_connection_file_content_matches_desktop_contract(
    scheduler_settings: Settings,
    isolated_config_dir: Path,
    fake_scheduler: FakeScheduler,
) -> None:
    """发布出去的就是桌面端要读的那两个字段。"""
    app = create_app(port=8877, publish_connection=True, settings=scheduler_settings)

    with TestClient(app):
        payload: dict[str, Any] = json.loads(
            (isolated_config_dir / "connection.json").read_text()
        )

    assert payload["port"] == 8877
    assert payload["token"]
