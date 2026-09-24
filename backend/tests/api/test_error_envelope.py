"""异常处理层的用例。

正常路由都自己 catch 了预期内的领域异常，所以 bootstrap/errors.py 的映射规则走不到。
这里挂几条临时路由把每条分支都触发一遍：客户端不管撞上哪种失败，拿到的都该是同一个
envelope 形状。

500 那条特别要紧：内部错误的原文不能进响应（可能带路径、SQL 片段），只能进日志。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.api.conftest import TEST_TOKEN

from fileseek.bootstrap.auth import TOKEN_HEADER
from fileseek.bootstrap.errors import INTERNAL_ERROR_MESSAGE
from fileseek.features.library.domain.exceptions import (
    FolderNotEmptyError,
    FolderNotFoundError,
)
from fileseek.shared.application.exceptions import ValidationError

SECRET = "内部细节：/Users/someone/secret.db"  # noqa: S105 - 测试用字面量


@pytest.fixture
def boom_client(app: FastAPI) -> TestClient:
    """挂上会抛各类异常的临时路由。"""

    @app.get("/boom/not-found")
    async def not_found() -> None:
        raise FolderNotFoundError("文件夹 f_1 不存在")

    @app.get("/boom/validation")
    async def validation() -> None:
        raise ValidationError("名字不能为空")

    @app.get("/boom/application")
    async def application() -> None:
        raise FolderNotEmptyError("文件夹非空")

    @app.get("/boom/unexpected")
    async def unexpected() -> None:
        raise RuntimeError(SECRET)

    # raise_server_exceptions=False：要的是 500 响应本身，而不是让异常冒到测试里。
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({TOKEN_HEADER: TEST_TOKEN})
    return client


def test_not_found_maps_to_404(boom_client: TestClient) -> None:
    response = boom_client.get("/boom/not-found")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["data"] is None
    assert "f_1" in body["error"]


def test_validation_maps_to_400(boom_client: TestClient) -> None:
    response = boom_client.get("/boom/validation")

    assert response.status_code == 400
    assert response.json()["error"] == "名字不能为空"


def test_application_error_maps_to_400(boom_client: TestClient) -> None:
    """一般业务异常是调用方能纠正的问题，所以报文原文照传。"""
    response = boom_client.get("/boom/application")

    assert response.status_code == 400
    assert response.json()["error"] == "文件夹非空"


def test_unexpected_error_maps_to_500(boom_client: TestClient) -> None:
    response = boom_client.get("/boom/unexpected")

    assert response.status_code == 500
    assert response.json()["status"] == "error"


def test_unexpected_error_does_not_leak_details(boom_client: TestClient) -> None:
    """内部细节只进日志，不进响应。"""
    body = boom_client.get("/boom/unexpected").json()

    assert body["error"] == INTERNAL_ERROR_MESSAGE
    assert SECRET not in body["error"]


def test_unknown_route_is_wrapped_in_envelope(client: TestClient) -> None:
    """连 404 路由也是 envelope，客户端不用认 Starlette 的 {"detail": ...}。"""
    response = client.get("/api/v1/no-such-endpoint")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert "detail" not in body


def test_method_not_allowed_is_wrapped_in_envelope(client: TestClient) -> None:
    response = client.patch("/api/v1/library/folders")

    assert response.status_code == 405
    assert response.json()["status"] == "error"
