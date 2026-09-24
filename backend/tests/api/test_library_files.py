"""文件列表与批量删除 API 用例。

一个容易被误用的点：`GET /library/files?folder=` 传的是文件夹**名字**，不是 id
（`ListFilesUseCase` 内部先 `get_by_name`）。名字查不到时返回空列表而不是报错。

批量删除会真的动磁盘（`AddFiles2RecycleUseCase` 调 `compress()` 把文件压进回收站），
所以那几个用例要用 `tmp_path` 下真实存在的文件，不能用默认的 `/seeded/...` 假路径。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from tests.api.conftest import API

FILES = f"{API}/library/files"


def _real_file(seed: Any, tmp_path: Path, file_id: str, name: str, **kwargs: Any) -> Path:
    """造一个磁盘上真实存在的文件并入库。

    批量删除会把文件压进回收站（`AddFiles2RecycleUseCase` 调 `compress()`），
    默认的 `/seeded/...` 是个不存在的路径，用它会 500。
    """
    target = tmp_path / name
    target.write_bytes(b"content")
    seed.file(file_id=file_id, name=name, path=str(target), **kwargs)
    return target


def test_list_files_empty(client: TestClient) -> None:
    body = client.get(FILES).json()

    assert body["status"] == "success"
    assert body["data"] == []
    assert body["total"] == 0
    assert body["has_more"] is False


def test_list_files_shape(client: TestClient, seed: Any) -> None:
    seed.file(file_id="file_1", name="report.pdf", media_type="document", size=2048)

    body = client.get(FILES).json()

    file = body["data"][0]
    assert file["id"] == "file_1"
    assert file["name"] == "report.pdf"
    # 类型字段是大驼峰 `FileType`，这是既有契约。
    assert file["FileType"] == "document"
    # size 是字符串：JS 的 Number 放不下大文件的字节数而不丢精度。
    assert file["size"] == "2048"
    assert file["parentFolder"] is None


def test_list_files_filters_by_file_type(client: TestClient, seed: Any) -> None:
    seed.file(file_id="file_1", name="a.pdf", media_type="document")
    seed.file(file_id="file_2", name="b.jpg", media_type="image")

    body = client.get(FILES, params={"file_type": "image"}).json()

    assert [f["id"] for f in body["data"]] == ["file_2"]
    assert body["total"] == 1


def test_list_files_filters_by_folder_name(client: TestClient, seed: Any) -> None:
    """folder 参数是名字，不是 id。"""
    seed.folder(folder_id="f_1", name="文档")
    seed.file(file_id="file_1", name="a.pdf", parent_folder="f_1")
    seed.file(file_id="file_2", name="b.pdf", parent_folder=None)

    body = client.get(FILES, params={"folder": "文档"}).json()

    assert [f["id"] for f in body["data"]] == ["file_1"]


def test_list_files_unknown_folder_name_is_empty_not_error(
    client: TestClient, seed: Any
) -> None:
    seed.file(file_id="file_1")

    body = client.get(FILES, params={"folder": "不存在的文件夹"}).json()

    assert body["status"] == "success"
    assert body["data"] == []
    assert body["total"] == 0


def test_list_files_pagination(client: TestClient, seed: Any) -> None:
    for index in range(5):
        seed.file(file_id=f"file_{index}", name=f"f{index}.pdf")

    body = client.get(FILES, params={"page": 1, "page_size": 2}).json()

    assert len(body["data"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == 5
    assert body["has_more"] is True


def test_list_files_last_page_has_no_more(client: TestClient, seed: Any) -> None:
    for index in range(3):
        seed.file(file_id=f"file_{index}", name=f"f{index}.pdf")

    body = client.get(FILES, params={"page": 2, "page_size": 2}).json()

    assert len(body["data"]) == 1
    assert body["has_more"] is False


def test_list_files_rejects_page_size_over_limit(client: TestClient) -> None:
    response = client.get(FILES, params={"page_size": 101})

    assert response.status_code == 422
    assert response.json()["status"] == "error"


def test_list_files_rejects_zero_page(client: TestClient) -> None:
    assert client.get(FILES, params={"page": 0}).status_code == 422


def test_batch_delete_moves_files_to_recycle(
    client: TestClient, seed: Any, tmp_path: Path
) -> None:
    _real_file(seed, tmp_path, "file_1", "a.pdf")
    _real_file(seed, tmp_path, "file_2", "b.pdf")

    response = client.post(f"{FILES}/batch-delete", json={"file_ids": ["file_1"]})

    assert response.status_code == 200
    assert response.json() == {"status": "success", "data": None, "error": None}

    remaining = client.get(FILES).json()["data"]
    assert [f["id"] for f in remaining] == ["file_2"]

    recycled = client.get(f"{API}/library/recycle").json()["data"]
    assert [item["original_file_id"] for item in recycled] == ["file_1"]


def test_batch_delete_decrements_folder_count(
    client: TestClient, seed: Any, tmp_path: Path
) -> None:
    seed.folder(folder_id="f_1", name="文档", file_count=1)
    _real_file(seed, tmp_path, "file_1", "a.pdf", parent_folder="f_1")

    client.post(f"{FILES}/batch-delete", json={"file_ids": ["file_1"]})

    folders = client.get(f"{API}/library/folders").json()["data"]
    assert folders[0]["file_count"] == 0


def test_batch_delete_skips_unknown_ids(
    client: TestClient, seed: Any, tmp_path: Path
) -> None:
    """未知 id 被跳过而非报错：批量操作里一个失效 id 不该让整批失败。"""
    _real_file(seed, tmp_path, "file_1", "a.pdf")

    response = client.post(
        f"{FILES}/batch-delete",
        json={"file_ids": ["file_1", "does-not-exist"]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert client.get(FILES).json()["data"] == []


def test_batch_delete_empty_list_is_noop(
    client: TestClient, seed: Any, tmp_path: Path
) -> None:
    _real_file(seed, tmp_path, "file_1", "a.pdf")

    response = client.post(f"{FILES}/batch-delete", json={"file_ids": []})

    assert response.status_code == 200
    assert len(client.get(FILES).json()["data"]) == 1
