"""健康检查与鉴权的 API 用例。

这两件事是所有其他接口的前置条件：桌面端先靠 /health 判断后端就绪，再带 token 打
业务接口。它们错了，其他接口对不对都无从谈起。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.api.conftest import API, TEST_TOKEN

from fileseek.bootstrap.auth import TOKEN_HEADER


def test_health_needs_no_token(anon_client: TestClient) -> None:
    """/health 必须免鉴权：桌面端轮询它时还没读到 token。"""
    response = anon_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    # 形状是和桌面端 sidecar.rs::health_check_ok 的硬约定。
    assert body["data"]["status"] == "ok"


def test_health_reports_scheduler_state(client: TestClient) -> None:
    """健康检查如实反映调度器状态。

    调度器没有禁用开关，启动后总是在跑（测试里它被换成了不做事的替身，
    见 tests/api/conftest.py）。
    """
    body = client.get("/health").json()

    assert body["data"]["scheduler_running"] is True
    assert body["data"]["active_tasks"] == 0
    assert body["data"]["version"]


def test_api_docs_are_public(anon_client: TestClient) -> None:
    """文档页面及其 OpenAPI 描述可直接在本机浏览器打开。"""
    docs = anon_client.get("/docs")
    openapi = anon_client.get("/openapi.json")

    assert docs.status_code == 200
    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "FileSeek"
    assert openapi.json()["components"]["securitySchemes"]["FileSeekToken"] == {
        "type": "apiKey",
        "in": "header",
        "name": TOKEN_HEADER,
        "description": "启动后从 connection.json 读取 token",
    }


def test_business_endpoint_rejects_missing_token(anon_client: TestClient) -> None:
    """没有 token 一律 401，且响应仍是统一 envelope。"""
    response = anon_client.get(f"{API}/library/folders")

    assert response.status_code == 401
    body = response.json()
    assert body["status"] == "error"
    assert body["data"] is None
    assert body["error"]


def test_business_endpoint_rejects_wrong_token(anon_client: TestClient) -> None:
    response = anon_client.get(
        f"{API}/library/folders",
        headers={TOKEN_HEADER: "wrong-token"},
    )

    assert response.status_code == 401


def test_valid_token_is_accepted(client: TestClient) -> None:
    response = client.get(f"{API}/library/folders")

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_cross_origin_request_is_refused(client: TestClient) -> None:
    """带 token 但来自外部源：403。

    浏览器能自由访问 127.0.0.1，所以仅有 token 不足以判断请求可信。
    """
    response = client.get(
        f"{API}/library/folders",
        headers={"Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert response.json()["error"]


def test_non_browser_request_is_allowed(client: TestClient) -> None:
    """不带任何浏览器头的请求放行——桌面端 Rust 侧就是这样发请求的。"""
    response = client.get(f"{API}/library/folders")

    assert response.status_code == 200


def test_same_origin_fetch_metadata_is_allowed(client: TestClient) -> None:
    """我们自己页面发起的同源请求放行。"""
    response = client.get(
        f"{API}/library/folders",
        headers={"Sec-Fetch-Site": "same-origin"},
    )

    assert response.status_code == 200


def test_cross_site_fetch_metadata_is_refused(client: TestClient) -> None:
    response = client.get(
        f"{API}/library/folders",
        headers={"Sec-Fetch-Site": "cross-site"},
    )

    assert response.status_code == 403


def test_token_header_name_matches_desktop_contract() -> None:
    """头名字写死在 Rust 侧（connection.rs 的 TOKEN_HEADER），改了桌面端就连不上。"""
    assert TOKEN_HEADER == "X-FileSeek-Token"
    assert TEST_TOKEN  # 固定 token 供其他用例复用
