"""鉴权：token 校验与同源校验。

除健康检查和本地 API 文档外，每个请求都必须带上启动时发布到连接文件的 token，并且来自同源
上下文。两道防线各自解决一个问题：

1. token 挡住任意进程。只监听 loopback 是不够的——浏览器可以自由访问
   127.0.0.1，否则用户随便打开的一个网页就能往文件库里塞文件、或者把库读出去。

2. 同源校验挡住浏览器上下文，即使它不知怎么拿到了 token。合法客户端要么不是
   浏览器（桌面端从 Rust 侧发请求），要么是我们自己提供的页面。
"""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from fileseek.shared.envelope import error_response

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.responses import Response

logger = logging.getLogger(__name__)

TOKEN_HEADER = "X-FileSeek-Token"  # noqa: S105 - 头名字，不是密码

# 不鉴权：它只说明服务在不在，桌面端就是靠它判断后端起来了。
HEALTH_PATH = "/health"

# 文档页面需要继续请求 /openapi.json 才能渲染；这些页面只提供接口说明，不执行
# 业务操作。服务仅监听本机地址，因此允许直接在本机浏览器打开。
PUBLIC_PATHS = frozenset({HEALTH_PATH, "/docs", "/redoc", "/openapi.json"})

# 和 errors.py 的 INTERNAL_ERROR_MESSAGE 对应。BaseHTTPMiddleware 在自己的 task 里
# 跑 call_next，异常穿过 app 的 exception handler 后会冒到这里，不catch 住就变成
# 裸的 ASGI 失败而不是一个 500 响应。
INTERNAL_ERROR_MESSAGE = "请求未能完成，详情见服务日志"


def is_same_origin_request(request: Request) -> bool:
    """判断请求是否来自我们自己的源，或来自非浏览器客户端。

    浏览器会带 Origin（触发 CORS 的方法）或 Sec-Fetch-Site（同源导航）。两个都
    没有说明对方不是浏览器，那是桌面端 Rust 侧直接发的请求，放行。
    """
    origin = request.headers.get("Origin")
    if origin is not None:
        # 我们监听在 127.0.0.1，浏览器视 localhost 为不同源，所以这里按字面比较。
        expected = f"http://{request.url.hostname}:{request.url.port}"
        return origin == expected

    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site is not None:
        # "same-origin" 是我们自己的页面，"none" 是用户手敲地址栏的顶层导航，都行。
        return fetch_site in {"same-origin", "none"}

    # 完全没有浏览器头：对方不是浏览器，正是我们要放行的桌面端。
    return True


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """拒绝没有 token、或者来自外部源的请求。

    中间件跑在路由之前，所以鉴权集中在一处，而不是散落到每个 handler 上。
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        expected_token: str,
        public_paths: frozenset[str] = PUBLIC_PATHS,
    ) -> None:
        super().__init__(app)
        self.expected_token = expected_token
        self.public_paths = public_paths

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in self.public_paths:
            return await call_next(request)

        provided = request.headers.get(TOKEN_HEADER)
        # 用 compare_digest 而不是 !=：后者在首个不同字节就返回，能让愿意测时间的
        # 调用方逐字节猜出 token 前缀。
        if provided is None or not secrets.compare_digest(provided, self.expected_token):
            return JSONResponse(
                error_response("需要身份认证"),
                status_code=401,
            )

        if not is_same_origin_request(request):
            return JSONResponse(
                error_response("不允许跨源请求"),
                status_code=403,
            )

        try:
            return await call_next(request)
        except Exception:
            logger.exception(
                "处理 %s %s 时发生未捕获错误",
                request.method,
                request.url.path,
            )
            return JSONResponse(
                error_response(INTERNAL_ERROR_MESSAGE),
                status_code=500,
            )
