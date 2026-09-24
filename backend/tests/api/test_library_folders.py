"""文件夹 API 用例。

注意这一组接口的错误约定：业务失败（文件夹不存在、非空）返回 **HTTP 200** 加
error envelope，而不是 4xx——路由层自己 catch 了领域异常。这是现有契约，测试按它
断言；真正漏出去的异常才会被 bootstrap/errors.py 映射成状态码。
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from tests.api.conftest import API

FOLDERS = f"{API}/library/folders"


def test_list_folders_empty(client: TestClient) -> None:
    response = client.get(FOLDERS)

    assert response.status_code == 200
    assert response.json() == {"status": "success", "data": [], "error": None}


def test_list_folders_returns_seeded(client: TestClient, seed: Any) -> None:
    seed.folder(folder_id="f_1", name="文档", icon_type="icon-doc", file_count=3)

    body = client.get(FOLDERS).json()

    assert len(body["data"]) == 1
    folder = body["data"][0]
    assert folder["id"] == "f_1"
    assert folder["name"] == "文档"
    # 响应用 camelCase 的 iconType，库里是 snake_case 的 icon_type。
    assert folder["iconType"] == "icon-doc"
    assert folder["file_count"] == 3


def test_create_folder(client: TestClient) -> None:
    response = client.post(
        FOLDERS,
        json={"name": "图片", "iconType": "icon-image", "description": "我的图片"},
    )

    assert response.status_code == 200
    folder = response.json()["data"]
    assert folder["name"] == "图片"
    assert folder["iconType"] == "icon-image"
    assert folder["description"] == "我的图片"
    assert folder["file_count"] == 0
    # 文件夹 id 的前缀是 `d`（见 create_folder 的 generate_id("d")）。
    assert folder["id"].startswith("d")


def test_created_folder_is_persisted(client: TestClient) -> None:
    """创建后能被列出来——验的是整条链路真的写进了库，不只是回显入参。"""
    created = client.post(
        FOLDERS,
        json={"name": "视频", "iconType": "icon-video"},
    ).json()["data"]

    listed = client.get(FOLDERS).json()["data"]

    assert [f["id"] for f in listed] == [created["id"]]


def test_create_folder_defaults_description(client: TestClient) -> None:
    folder = client.post(
        FOLDERS,
        json={"name": "无描述", "iconType": "icon-x"},
    ).json()["data"]

    assert folder["description"] == ""


def test_create_folder_rejects_missing_icon_type(client: TestClient) -> None:
    """缺必填字段 → 422，由 bootstrap/errors.py 包成 envelope。"""
    response = client.post(FOLDERS, json={"name": "缺字段"})

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["data"] is None
    assert "iconType" in body["error"]


def test_update_folder(client: TestClient, seed: Any) -> None:
    seed.folder(folder_id="f_1", name="旧名", icon_type="icon-old")

    response = client.put(
        f"{FOLDERS}/f_1",
        json={"name": "新名", "iconType": "icon-new", "description": "改过了"},
    )

    assert response.status_code == 200
    folder = response.json()["data"]
    assert folder["name"] == "新名"
    assert folder["iconType"] == "icon-new"
    assert folder["description"] == "改过了"


def test_update_missing_folder_returns_error_envelope(client: TestClient) -> None:
    response = client.put(
        f"{FOLDERS}/nope",
        json={"name": "x", "iconType": "icon-x"},
    )

    # 200 + error envelope，见模块 docstring。
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["data"] is None
    assert "nope" in body["error"]


def test_delete_empty_folder(client: TestClient, seed: Any) -> None:
    seed.folder(folder_id="f_1", file_count=0)

    response = client.delete(f"{FOLDERS}/f_1")

    assert response.status_code == 200
    assert response.json() == {"status": "success", "data": None, "error": None}
    assert client.get(FOLDERS).json()["data"] == []


def test_delete_non_empty_folder_is_refused(client: TestClient, seed: Any) -> None:
    """非空文件夹不能删：否则里面的文件会变成无主记录。"""
    seed.folder(folder_id="f_1", file_count=2)

    body = client.delete(f"{FOLDERS}/f_1").json()

    assert body["status"] == "error"
    assert body["error"]
    # 仍然在库里。
    assert len(client.get(FOLDERS).json()["data"]) == 1


def test_delete_missing_folder_returns_error_envelope(client: TestClient) -> None:
    body = client.delete(f"{FOLDERS}/nope").json()

    assert body["status"] == "error"
    assert "nope" in body["error"]
