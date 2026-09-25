"""服务的启动与关闭。

启动顺序：建目录 → 建表 → 捞回上次遗留的在飞任务 → 起调度器 → 发布连接文件。

连接文件放在最后，因为它就是"就绪"信号：桌面端一读到它就开始打接口。提前发布
会让第一批请求打在还没建表的库上。

关闭顺序是反的，而且同样不能调换：先停止领新任务，等在飞的任务落地，再撤掉连接
文件、关库。反过来做会在任务还在写库的时候把连接抽走。

关闭路径上的每一步都要能在协作者已经不在了的时候不炸——关闭本身失败没有第二次
机会，而且会盖掉真正的退出原因。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fileseek.bootstrap import connection
from fileseek.bootstrap.container import Container, build_task_scheduler
from fileseek.config.paths import AppPaths, LibraryPaths
from fileseek.infrastructure.database.connection import close_db, init_db

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """装配、启动、并在退出时收拾干净。

    需要的开关都从 `app.state` 上取，由 `create_app` 放好：`port`、
    `publish_connection`、`auth_token`。
    """
    container: Container = app.state.container
    settings = container.settings

    app_paths = AppPaths.resolve()
    app_paths.ensure_directories()

    LibraryPaths(settings.lib_root).ensure_directories()
    await init_db()
    scheduler = build_task_scheduler(settings)
    # 捞回上次运行遗留的在飞任务，这一步和调度器开关无关：那些状态停在 processing
    # 的任务谁也不会去取，用户看到的是"卡在处理中"的一堆文件。
    released = await scheduler.release_stranded()
    if released:
        logger.info("启动时放回 %d 个上次遗留的任务", len(released))

    # 调度器总是启动，没有关掉它的开关：关掉它入库的文件会一直停在 queued，
    # 表现成"导入了但搜不到"，而这个故障从界面上看不出原因。测试要避开真实处理流程
    # 时替换 `build_task_scheduler`（见 tests/api/conftest.py），而不是不启动它。
    scheduler.start()
    container.scheduler = scheduler
    logger.info("任务调度器已启动（轮询间隔 %.1fs）", settings.task_poll_interval)
    port: int | None = getattr(app.state, "port", None)
    if getattr(app.state, "publish_connection", False) and port is not None:
        connection.publish(app_paths.connection_file, port, app.state.auth_token)

    try:
        yield
    finally:
        await _shutdown(app, container, app_paths)


async def _shutdown(app: FastAPI, container: Container, app_paths: AppPaths) -> None:
    """按固定顺序收尾，每一步都自己兜住异常。

    一步失败不该让后面的步骤不执行：连接文件留在原地会让客户端一直连一个没人
    监听的端口，比任何一个单步的错误都更难排查。
    """
    if container.scheduler is not None:
        try:
            released = await container.scheduler.shutdown(settings_timeout(container))
            if released:
                logger.info("关闭时放回 %d 个未落地的任务", len(released))
        except Exception:
            logger.exception("任务调度器关闭失败")
        finally:
            container.scheduler = None

    if getattr(app.state, "publish_connection", False):
        try:
            connection.revoke(app_paths.connection_file)
        except Exception:
            logger.exception("连接文件清理失败")


    try:
        await close_db()
    except Exception:
        logger.exception("数据库关闭失败")

    logger.info("服务已关闭")


def settings_timeout(container: Container) -> float:
    """关闭时给在飞任务的时限。"""
    return container.settings.task_drain_timeout
