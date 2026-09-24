"""系统设置与 NAS 探测的 API 用例。

NAS 测试只探端口可达性（`TestNASConnectionUseCase` 用 socket 连一下），不做协议握手。
这里用一个保证连不上的地址来验失败路径，不碰真实网络。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.api.conftest import API

SETTINGS = f"{API}/settings"


def test_get_settings_falls_back_to_config_default(
    client: TestClient, lib_root: Path
) -> None:
    """settings 表还没有行时，返回配置里的库根目录而不是报错。"""
    body = client.get(SETTINGS).json()

    assert body["status"] == "success"
    assert body["data"]["lib_root"] == str(lib_root)
    assert body["data"]["nas_enabled"] is False


def test_update_settings_persists_new_root(client: TestClient, tmp_path: Path) -> None:
    new_root = tmp_path / "new-library"
    new_root.mkdir()

    response = client.post(SETTINGS, json={"lib_root": str(new_root)})

    assert response.status_code == 200
    assert response.json()["data"]["lib_root"] == str(new_root)
    # 读回来确认落了库，而不只是回显。
    assert client.get(SETTINGS).json()["data"]["lib_root"] == str(new_root)


def test_update_settings_creates_missing_directory(
    client: TestClient, tmp_path: Path
) -> None:
    """路径不存在时创建它——用户在设置里填一个新目录是正常操作。"""
    target = tmp_path / "does-not-exist-yet"

    response = client.post(SETTINGS, json={"lib_root": str(target)})

    assert response.status_code == 200
    assert target.is_dir()


def test_update_settings_refuses_a_file_path(
    client: TestClient, tmp_path: Path
) -> None:
    not_a_dir = tmp_path / "a-file.txt"
    not_a_dir.write_text("x")

    body = client.post(SETTINGS, json={"lib_root": str(not_a_dir)}).json()

    assert body["status"] == "error"
    assert body["error"]


def test_update_settings_rejects_missing_field(client: TestClient) -> None:
    response = client.post(SETTINGS, json={})

    assert response.status_code == 422
    assert response.json()["status"] == "error"


def test_nas_test_rejects_unsupported_protocol(client: TestClient) -> None:
    """协议不认识时直接报错，不会去连网络。"""
    body = client.post(
        f"{SETTINGS}/nas/test",
        json={
            "protocol": "ftp",
            "host": "nas.local",
            "share_path": "/share",
            "username": "u",
            "password": "p",
        },
    ).json()

    assert body["status"] == "error"
    assert "ftp" in body["error"]


def test_nas_test_reports_unreachable_host(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """连不上时返回 error envelope 而不是抛异常。

    socket 被打桩：真连一个不可达地址要等满 3 秒超时，而且结果取决于跑测试的网络
    （某些网络会应答任意地址，那样这个用例就假过）。
    """

    def refuse(*_args: object, **_kwargs: object) -> object:
        raise OSError("Connection refused")

    monkeypatch.setattr(
        "fileseek.features.settings.application.use_cases.test_nas_connection"
        ".socket.create_connection",
        refuse,
    )

    body = client.post(
        f"{SETTINGS}/nas/test",
        json={
            "protocol": "smb",
            "host": "nas.local",
            "share_path": "/share",
            "username": "u",
            "password": "p",
        },
    ).json()

    assert body["status"] == "error"
    assert "nas.local" in body["error"]


def test_nas_test_succeeds_when_port_is_reachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """端口可达 → success。注意这只验证了网络可达性，没有校验凭据。"""

    class DummySocket:
        def __enter__(self) -> DummySocket:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

    monkeypatch.setattr(
        "fileseek.features.settings.application.use_cases.test_nas_connection"
        ".socket.create_connection",
        lambda *_a, **_k: DummySocket(),
    )

    body = client.post(
        f"{SETTINGS}/nas/test",
        json={
            "protocol": "smb",
            "host": "nas.local",
            "share_path": "/share",
            "username": "u",
            "password": "p",
        },
    ).json()

    assert body["status"] == "success"
    assert body["data"] == "Connection successful!"


def test_nas_test_rejects_missing_fields(client: TestClient) -> None:
    response = client.post(f"{SETTINGS}/nas/test", json={"protocol": "smb"})

    assert response.status_code == 422


def test_recent_access_list(client: TestClient, seed: Any) -> None:
    seed.file(file_id="file_1")
    seed.recent_access(file_id="file_1", accessed_at="2026-01-04T00:00:00+00:00")

    body = client.get(f"{API}/library/recent").json()

    assert body["status"] == "success"
    assert body["data"] == [
        {"file_id": "file_1", "accessed_at": "2026-01-04T00:00:00+00:00"}
    ]


def test_recent_access_empty(client: TestClient) -> None:
    assert client.get(f"{API}/library/recent").json()["data"] == []


def test_recent_access_respects_limit(client: TestClient, seed: Any) -> None:
    seed.file(file_id="file_1")
    for day in range(1, 4):
        seed.recent_access(file_id="file_1", accessed_at=f"2026-01-0{day}T00:00:00+00:00")

    body = client.get(f"{API}/library/recent", params={"limit": 2}).json()

    assert len(body["data"]) == 2


def test_recent_access_rejects_bad_limit(client: TestClient) -> None:
    assert client.get(f"{API}/library/recent", params={"limit": 0}).status_code == 422
    assert client.get(f"{API}/library/recent", params={"limit": 101}).status_code == 422
