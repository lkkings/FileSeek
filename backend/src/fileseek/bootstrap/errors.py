"""统一异常处理。

路由层已经把大部分预期内的业务异常就地转成了 error envelope，这里兜住漏出来的：
没被 catch 的领域异常、请求体校验失败、以及任何未预料的崩溃。

不管走哪条路，客户端拿到的都是同一个 envelope 形状（status/data/error），所以
它不需要区分"业务失败"和"框架报错"两种响应格式。
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.shared.domain.exceptions import (
    ApplicationError,
    InferenceError,
    NotFoundError,
    ValidationError,
)
from fileseek.shared.envelope import error_response

logger = logging.getLogger(__name__)

# 不把异常原文透给客户端：里面可能有路径、SQL 片段这类不该外泄的细节。
INTERNAL_ERROR_MESSAGE = "请求未能完成，详情见服务日志"


async def handle_not_found(_request: Request, exc: Exception) -> JSONResponse:
    """资源不存在 → 404。"""
    return JSONResponse(error_response(str(exc)), status_code=404)


async def handle_validation(_request: Request, exc: Exception) -> JSONResponse:
    """领域校验失败 → 400。"""
    return JSONResponse(error_response(str(exc)), status_code=400)


async def handle_application_error(_request: Request, exc: Exception) -> JSONResponse:
    """其余业务异常 → 400。

    它们是调用方能理解并纠正的问题（文件夹非空、NAS 连不上），不是服务端故障，
    所以报文原文照传。
    """
    return JSONResponse(error_response(str(exc)), status_code=400)


async def handle_source_unavailable(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """索引存在但来源不可获取 → 410。"""
    return JSONResponse(error_response(str(exc)), status_code=410)


async def handle_request_validation(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """请求体/查询参数不合法 → 422，并保留 FastAPI 的字段级报错。"""
    errors_fn: Callable[[], list[object]] = getattr(exc, "errors", list)
    detail = errors_fn()
    return JSONResponse(
        error_response(f"请求参数不合法: {detail}"),
        status_code=422,
    )


async def handle_http_exception(_request: Request, exc: Exception) -> JSONResponse:
    """把 HTTPException 也包成 envelope。

    媒体流路由用 HTTPException 报 404/416，不接这个 handler 的话它会走 Starlette
    默认的 `{"detail": ...}`，客户端就得认两种错误格式。
    """
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101 - 由注册类型保证
    return JSONResponse(
        error_response(str(exc.detail)),
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def handle_inference_error(_request: Request, exc: Exception) -> JSONResponse:
    """模型推理不可用 → 503。

    查询模型进程崩溃、超时或处于崩溃冷却期时走这里。单独给 503 而不是落进兜底的 500：
    这是暂时性故障，下一次请求会自动重启进程，前端可以据此提示"稍后重试"。
    不降级成空结果——那会让用户以为"没有搜到"。报文不含路径等细节，原样透传。
    """
    logger.warning("模型推理不可用: %s", exc)
    return JSONResponse(error_response(f"搜索服务暂时不可用，请稍后重试（{exc}）"), status_code=503)


async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    """兜底 → 500。原因只进日志，不进响应。"""
    logger.exception(
        "处理 %s %s 时发生未捕获错误",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        error_response(INTERNAL_ERROR_MESSAGE),
        status_code=500,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全部异常处理器。

    注册顺序不决定匹配优先级——Starlette 按异常类的 MRO 找最接近的注册项，
    所以 NotFoundError 命中自己的 handler 而不是 ApplicationError 的。
    """
    app.add_exception_handler(NotFoundError, handle_not_found)
    app.add_exception_handler(SourceUnavailableError, handle_source_unavailable)
    app.add_exception_handler(ValidationError, handle_validation)
    app.add_exception_handler(ApplicationError, handle_application_error)
    app.add_exception_handler(InferenceError, handle_inference_error)
    app.add_exception_handler(RequestValidationError, handle_request_validation)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected)
