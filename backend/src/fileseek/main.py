"""服务进程入口。

推荐的启动方式（也是桌面端 sidecar 用的那条）：

    python -m fileseek

它自己探测空闲端口、把 `{port, token}` 发布到连接文件、再把服务跑起来。端口不写死
是因为桌面端并不指定端口——它读连接文件来得知后端绑在哪儿，所以这里能自由挑一个
没被占用的。

只监听 127.0.0.1：文件库里是用户的私有文件，没有任何理由暴露到网络上。
"""

from __future__ import annotations

import logging
import socket

import click
import uvicorn

from fileseek.bootstrap import configure_logging, create_app
from fileseek.config.paths import AppPaths
from fileseek.config.settings import get_settings

logger = logging.getLogger(__name__)


def find_free_port(host: str, preferred: int) -> int:
    """返回一个可用端口：能拿到 preferred 就用它，否则让内核挑一个。

    这里探测完就把 socket 关掉，真正的 bind 由 uvicorn 做，中间有一个很小的窗口
    可能被别的进程抢走。这是可以接受的：抢占会让启动直接失败并报错，而不是静默
    地连到别人的服务上。用固定端口反而更糟——端口被占时每次启动都失败。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, preferred))
        except OSError:
            logger.info("端口 %d 已被占用，改用内核分配的空闲端口", preferred)
        else:
            return preferred

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--host",
    default=None,
    help="监听地址，默认 127.0.0.1。改成对外地址会把文件库暴露到网络上。",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help="监听端口。被占用时自动改用空闲端口；不指定则从配置取。",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR"],
        case_sensitive=False,
    ),
    help="日志级别。",
)
def main(
    host: str | None,
    port: int | None,
    log_level: str,
) -> int:
    """启动 FileSeek 后端服务。"""
    settings = get_settings()

    app_paths = AppPaths.resolve()
    app_paths.ensure_directories()
    configure_logging(level=log_level, log_file=app_paths.log_file)

    resolved_host = host if host is not None else settings.api_host
    resolved_port = find_free_port(resolved_host, port or settings.api_port)

    # 连接文件由 lifespan 在建表之后发布：它就是"就绪"信号，早发布会让桌面端
    # 把请求打在还没准备好的库上。
    app = create_app(port=resolved_port, publish_connection=True)

    logger.info("FileSeek 服务启动于 http://%s:%d", resolved_host, resolved_port)

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=resolved_host,
            port=resolved_port,
            log_level=log_level.lower(),
            # 日志已由 configure_logging 配好（同时进 stderr 和文件），交给 uvicorn
            # 重配会把文件那一路顶掉。
            log_config=None,
        )
    )
    # `POST /shutdown` 直接置停止标志，和收到 SIGTERM 走同一条收尾路径。
    app.state.request_shutdown = lambda: setattr(server, "should_exit", True)
    server.run()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
