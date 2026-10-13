"""`POST /shutdown`：桌面端在 Windows 上请求后端优雅停止的入口。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_shutdown_needs_the_token(app, client: TestClient) -> None:
    requested: list[bool] = []
    app.state.request_shutdown = lambda: requested.append(True)

    response = client.post("/shutdown")

    assert response.status_code == 401
    assert requested == []


def test_shutdown_requests_a_graceful_stop(app, auth_client: TestClient) -> None:
    requested: list[bool] = []
    app.state.request_shutdown = lambda: requested.append(True)

    response = auth_client.post("/shutdown")

    assert response.status_code == 200
    assert response.json()["data"] == {"stopping": True}
    assert requested == [True]


def test_shutdown_rejects_cross_origin_requests(app, auth_client: TestClient) -> None:
    requested: list[bool] = []
    app.state.request_shutdown = lambda: requested.append(True)

    response = auth_client.post("/shutdown", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert requested == []
