"""FastAPI 应用的装配。

`create_app()` 装出一个完整可用的应用——路由、鉴权、异常处理、lifespan 全都接好。
它不需要额外的"注入协作者"步骤：请求作用域的依赖由各 feature 的 dependencies 经
`Depends` 自行解析，长生命周期的协作者由 lifespan 装到 `app.state.container` 上。

`create_service_app()` 是给 `uvicorn --factory` 用的薄封装：uvicorn 自己持有 socket，
所以端口只能靠环境变量 `FILESEEK_PORT` 告知，而且它要额外发布连接文件。
"""

from __future__ import annotations

import logging
import os
import signal

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from fileseek.bootstrap.auth import HEALTH_PATH, SHUTDOWN_PATH, TOKEN_HEADER, TokenAuthMiddleware
from fileseek.bootstrap.connection import generate_token
from fileseek.bootstrap.container import Container
from fileseek.bootstrap.dependencies import build_http_dependencies
from fileseek.bootstrap.errors import register_exception_handlers
from fileseek.bootstrap.lifespan import lifespan
from fileseek.config.settings import Settings, get_settings
from fileseek.features.library.interfaces.http import router as library_router
from fileseek.features.recent.interfaces.http.routers import router as recent_router
from fileseek.features.recycle.interfaces.http.routers import router as recycle_router
from fileseek.features.search.interfaces.http import router as search_router
from fileseek.features.settings.interfaces.http import router as settings_router

from fileseek.features.tasks.interfaces.http import router as tasks_router
from fileseek.shared.envelope import success_response

logger = logging.getLogger(__name__)

# uvicorn --factory 模式下告知端口用的环境变量：那种模式下 socket 由 uvicorn 持有，
# 应用自己不知道最终绑到了哪个端口。
PORT_ENV_VAR = "FILESEEK_PORT"


def _signal_self() -> None:
    """让 uvicorn 以为收到了 Ctrl+C。Windows 上 SIGINT 同样可用，SIGTERM 不行。"""
    signal.raise_signal(signal.SIGINT)


def create_app(
    *,
    port: int | None = None,
    publish_connection: bool = False,
    auth_token: str | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """装配应用。

    Args:
        port: 服务实际监听的端口，写进连接文件用。None 表示调用方也不知道
            （测试里用 TestClient 就是这种情况）。
        publish_connection: 是否发布/清理连接文件。只有真正在监听端口的进程
            该发布它，否则会把桌面端指到一个没人监听的端口上。
        auth_token: 本次运行的 token，默认随机生成。测试传一个固定值更方便。
        settings: 配置，默认取全局单例。
    """
    resolved_settings = settings if settings is not None else get_settings()
    token = auth_token if auth_token is not None else generate_token()

    app = FastAPI(
        title="FileSeek",
        description="Local-first semantic file search backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.container = Container(settings=resolved_settings)
    app.state.settings = resolved_settings
    app.state.dependencies = build_http_dependencies(resolved_settings)
    app.state.port = port
    app.state.publish_connection = publish_connection
    app.state.auth_token = token
    # 默认向自身发 SIGINT，uvicorn 收到后和 SIGTERM 一样走优雅关闭；`main()` 持有
    # uvicorn.Server 时换成直接置 should_exit，不经过信号。
    app.state.request_shutdown = _signal_self

    register_exception_handlers(app)

    # 鉴权装在最外层：它要在路由之前拦下没有 token 的请求。
    app.add_middleware(TokenAuthMiddleware, expected_token=token)

    def custom_openapi() -> dict[str, object]:
        """Expose the custom token header to Swagger UI's Authorize dialog."""
        if app.openapi_schema is not None:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        components = schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes["FileSeekToken"] = {
            "type": "apiKey",
            "in": "header",
            "name": TOKEN_HEADER,
            "description": "启动后从 connection.json 读取 token",
        }
        schema["security"] = [{"FileSeekToken": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    # 不带 api 前缀，也不鉴权：桌面端靠它判断后端是否就绪，那时它还没读到 token。
    @app.get(HEALTH_PATH, tags=["health"])
    async def health() -> dict[str, object]:
        """健康检查。

        返回形状是和桌面端的约定：它检查 `data.status == "ok"`
        （`sidecar.rs::health_check_ok`）。
        """
        container: Container = app.state.container
        scheduler = container.scheduler
        return success_response(
            {
                "status": "ok",
                "version": app.version,
                "scheduler_running": scheduler.is_running if scheduler else False,
                "active_tasks": scheduler.active_count if scheduler else 0,
            }
        )

    # 不带 api 前缀，要 token：桌面端在 Windows 上靠它优雅停止后端——那里没有 SIGTERM，
    # 直接结束进程会跳过 lifespan 的收尾，在飞任务停在 processing、连接文件留在原地。
    # 只置停止标志，真正的收尾和 SIGTERM 一样由 uvicorn 走完 lifespan。
    @app.post(SHUTDOWN_PATH, tags=["health"])
    async def shutdown() -> dict[str, object]:
        """请求服务优雅停止。立即返回，收尾在响应发出后进行。"""
        app.state.request_shutdown()
        return success_response({"stopping": True})

    prefix = resolved_settings.api_prefix
    for feature_router in (
        library_router,
        recent_router,
        recycle_router,
        search_router,
        settings_router,
        tasks_router,

    ):
        app.include_router(feature_router, prefix=prefix)

    return app


def create_service_app() -> FastAPI:
    """给 `uvicorn --factory` 用的工厂：额外发布连接文件。

    端口从 `FILESEEK_PORT` 读，必须和 uvicorn 的 `--port` 一致——uvicorn 自己
    bind socket，应用问不到真实端口。没设这个变量就只装应用、不发布连接文件，
    此时桌面端连不上（它等的就是那个文件）。
    """
    raw_port = os.environ.get(PORT_ENV_VAR)
    port = int(raw_port) if raw_port else None

    if port is None:
        logger.warning(
            "%s 未设置：不会发布连接文件，桌面端无法连接。"
            "用 uvicorn --factory 时请设置它，值与 --port 一致",
            PORT_ENV_VAR,
        )

    return create_app(port=port, publish_connection=port is not None)
