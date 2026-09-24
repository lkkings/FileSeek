"""回收站 API 用例。

还原与永久删除会真的动文件（经 `FileSystemResolver` → `LocalFileSystemAdapter`），
所以这里用 `tmp_path` 下的真实文件，而不是 mock 掉文件系统——要验的正是"记录和磁盘
一起变"这件事。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from tests.api.conftest import API

RECYCLE = f"{API}/library/recycle"
FILES = f"{API}/library/files"


def test_list_recycle_empty(client: TestClient) -> None:
    body = client.get(RECYCLE).json()

    assert body["status"] == "success"
    assert body["data"] == []
    assert body["total"] == 0


def test_list_recycle_shape(client: TestClient, seed: Any) -> None:
    seed.recycle_item(
        item_id="r_1",
        original_file_id="file_1",
        original_name="report.pdf",
        size=4096,
    )

    item = client.get(RECYCLE).json()["data"][0]

    assert item["id"] == "r_1"
    assert item["original_file_id"] == "file_1"
    assert item["original_name"] == "report.pdf"
    # 回收站条目的类型字段是 `file_type`（小写下划线），文件列表那边是 `FileType`。
    assert item["file_type"] == "document"
    assert item["size"] == "4096"


def test_list_recycle_pagination(client: TestClient, seed: Any) -> None:
    for index in range(3):
        seed.recycle_item(item_id=f"r_{index}", original_file_id=f"file_{index}")

    body = client.get(RECYCLE, params={"page": 1, "page_size": 2}).json()

    assert len(body["data"]) == 2
    assert body["total"] == 3
    assert body["has_more"] is True


def test_restore_item_recreates_file_and_moves_it_back(
    client: TestClient, seed: Any, tmp_path: Path
) -> None:
    """还原后：文件记录回到 files 表，回收站记录消失。

    这里走完整链路（入库 → 批量删除 → 还原）而不是手工造回收站条目：删除时
    `AddFiles2RecycleUseCase` 会把文件压成一个包，并把**包的路径**记进
    `original_path`；还原再对它 `decompress()`。手工 seed 一个原始文件路径的话
    还原会去解压一个不是压缩包的文件。
    """
    original = tmp_path / "report.pdf"
    original.write_bytes(b"content")
    seed.file(file_id="file_1", name="report.pdf", path=str(original))
    client.post(f"{FILES}/batch-delete", json={"file_ids": ["file_1"]})

    item_id = client.get(RECYCLE).json()["data"][0]["id"]
    response = client.post(f"{RECYCLE}/{item_id}/restore")

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    restored = client.get(FILES).json()["data"]
    assert [f["id"] for f in restored] == ["file_1"]
    assert client.get(RECYCLE).json()["data"] == []


def test_restore_item_increments_folder_count(
    client: TestClient, seed: Any, tmp_path: Path
) -> None:
    original = tmp_path / "a.pdf"
    original.write_bytes(b"x")
    seed.folder(folder_id="f_1", name="文档", file_count=1)
    seed.file(file_id="file_1", name="a.pdf", path=str(original), parent_folder="f_1")
    client.post(f"{FILES}/batch-delete", json={"file_ids": ["file_1"]})
    assert client.get(f"{API}/library/folders").json()["data"][0]["file_count"] == 0

    item_id = client.get(RECYCLE).json()["data"][0]["id"]
    client.post(f"{RECYCLE}/{item_id}/restore")

    folders = client.get(f"{API}/library/folders").json()["data"]
    assert folders[0]["file_count"] == 1


def test_restore_missing_item_returns_error_envelope(client: TestClient) -> None:
    response = client.post(f"{RECYCLE}/nope/restore")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "nope" in body["error"]


def test_delete_permanently_removes_record_and_file(
    client: TestClient, seed: Any, tmp_path: Path
) -> None:
    target = tmp_path / "gone.pdf"
    target.write_bytes(b"bye")
    seed.recycle_item(item_id="r_1", original_path=str(target))

    response = client.delete(f"{RECYCLE}/r_1")

    assert response.status_code == 200
    assert client.get(RECYCLE).json()["data"] == []
    # 永久删除的意思是磁盘上也没了。
    assert not target.exists()


def test_delete_permanently_missing_item_returns_error_envelope(
    client: TestClient,
) -> None:
    body = client.delete(f"{RECYCLE}/nope").json()

    assert body["status"] == "error"
    assert "nope" in body["error"]


def test_clear_recycle_bin_removes_everything(
    client: TestClient, seed: Any, tmp_path: Path
) -> None:
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    seed.recycle_item(item_id="r_1", original_file_id="file_1", original_path=str(first))
    seed.recycle_item(item_id="r_2", original_file_id="file_2", original_path=str(second))

    response = client.delete(RECYCLE)

    assert response.status_code == 200
    assert client.get(RECYCLE).json()["data"] == []
    assert not first.exists()
    assert not second.exists()


def test_clear_empty_recycle_bin_is_noop(client: TestClient) -> None:
    response = client.delete(RECYCLE)

    assert response.status_code == 200
    assert response.json() == {"status": "success", "data": None, "error": None}
