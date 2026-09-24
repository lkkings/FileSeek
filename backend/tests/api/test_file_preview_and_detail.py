"""新增的三个接口：媒体流、单文件详情、访问记录。

这三条都是为桌面端对接补的：

- `GET /api/v1/library/files/preview/{file_id}` 返回原始字节而不是 envelope——
  `<img src>` / `<video src>` 读不懂信封。这个路径也正是 `POST /search` 响应里
  `preview_url` 指向的地址（见 search 的 `mappers._PREVIEW_PATH`），在它存在之前
  每条搜索结果的预览地址都是 404。
- `GET /api/v1/library/files/{file_id}` 补出"最近访问"要渲染的字段：
  `GET /library/recent` 只给 `{file_id, accessed_at}`。
- `POST /api/v1/library/files/{file_id}/access` 是 recent 表唯一的写入口。在它之前
  `RecordAccessUseCase` 已注册但没有任何 HTTP 路由，所以那张表永远是空的。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from tests.api.conftest import API

FILES = f"{API}/library/files"
RECENT = f"{API}/library/recent"


def _seed_real_file(seed: Any, tmp_path: Path, payload: bytes, name: str = "clip.mp4") -> Path:
    """造一个磁盘上真实存在的文件，并让库记录指向它。

    媒体流要真的把字节读出来，所以不能像别处那样用一个不存在的 `/seeded/...` 路径。
    """
    target = tmp_path / name
    target.write_bytes(payload)
    seed.file(file_id="file_1", name=name, path=str(target), size=len(payload))
    return target


class TestFilePreview:
    """`GET /api/v1/library/files/preview/{file_id}`。"""

    def test_returns_whole_file_without_range(
        self, client: TestClient, seed: Any, tmp_path: Path
    ) -> None:
        _seed_real_file(seed, tmp_path, b"0123456789")

        response = client.get(f"{FILES}/preview/file_1")

        assert response.status_code == 200
        assert response.content == b"0123456789"
        # 播放器靠这个头判断能不能 seek。
        assert response.headers["accept-ranges"] == "bytes"

    def test_content_type_is_guessed_from_the_name(
        self, client: TestClient, seed: Any, tmp_path: Path
    ) -> None:
        _seed_real_file(seed, tmp_path, b"\x00\x01", name="photo.png")

        response = client.get(f"{FILES}/preview/file_1")

        assert response.headers["content-type"].startswith("image/png")

    def test_unknown_extension_falls_back_to_octet_stream(
        self, client: TestClient, seed: Any, tmp_path: Path
    ) -> None:
        """猜不出类型也要能取到字节，让浏览器自己嗅探。"""
        _seed_real_file(seed, tmp_path, b"data", name="blob.zzz")

        response = client.get(f"{FILES}/preview/file_1")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/octet-stream")

    def test_range_returns_206_with_that_slice(
        self, client: TestClient, seed: Any, tmp_path: Path
    ) -> None:
        """这是 seek 的核心：只取请求的那一段，不下整个文件。"""
        _seed_real_file(seed, tmp_path, b"0123456789")

        response = client.get(f"{FILES}/preview/file_1", headers={"Range": "bytes=2-5"})

        assert response.status_code == 206
        assert response.content == b"2345"
        assert response.headers["content-range"] == "bytes 2-5/10"

    def test_open_ended_range_runs_to_the_last_byte(
        self, client: TestClient, seed: Any, tmp_path: Path
    ) -> None:
        _seed_real_file(seed, tmp_path, b"0123456789")

        response = client.get(f"{FILES}/preview/file_1", headers={"Range": "bytes=7-"})

        assert response.status_code == 206
        assert response.content == b"789"
        assert response.headers["content-range"] == "bytes 7-9/10"

    def test_suffix_range_returns_the_tail(
        self, client: TestClient, seed: Any, tmp_path: Path
    ) -> None:
        """`bytes=-N` 是"最后 N 个字节"，不是"到第 N 个字节"。"""
        _seed_real_file(seed, tmp_path, b"0123456789")

        response = client.get(f"{FILES}/preview/file_1", headers={"Range": "bytes=-3"})

        assert response.status_code == 206
        assert response.content == b"789"
        assert response.headers["content-range"] == "bytes 7-9/10"

    def test_range_past_the_end_is_clamped(
        self, client: TestClient, seed: Any, tmp_path: Path
    ) -> None:
        """末端超出文件时收敛到最后一个字节，RFC 9110 允许这样。"""
        _seed_real_file(seed, tmp_path, b"01234")

        response = client.get(f"{FILES}/preview/file_1", headers={"Range": "bytes=3-999"})

        assert response.status_code == 206
        assert response.content == b"34"
        assert response.headers["content-range"] == "bytes 3-4/5"

    def test_start_beyond_the_end_is_416(
        self, client: TestClient, seed: Any, tmp_path: Path
    ) -> None:
        _seed_real_file(seed, tmp_path, b"01234")

        response = client.get(f"{FILES}/preview/file_1", headers={"Range": "bytes=99-"})

        assert response.status_code == 416
        assert response.headers["content-range"] == "bytes */5"

    def test_unparsable_range_is_ignored_not_rejected(
        self, client: TestClient, seed: Any, tmp_path: Path
    ) -> None:
        """语法不认识就当没提这个要求，回整个文件——比 416 宽容，也符合 RFC。"""
        _seed_real_file(seed, tmp_path, b"01234")

        response = client.get(f"{FILES}/preview/file_1", headers={"Range": "rows=1-2"})

        assert response.status_code == 200
        assert response.content == b"01234"

    def test_missing_record_is_404_envelope(self, client: TestClient) -> None:
        """出错时才回退成 envelope：那时本来就没有可播放的内容。"""
        response = client.get(f"{FILES}/preview/nope")

        assert response.status_code == 404
        body = response.json()
        assert body["status"] == "error"
        assert "nope" in body["error"]

    def test_record_without_the_file_on_disk_is_404(
        self, client: TestClient, seed: Any
    ) -> None:
        """记录还在但文件被库外删掉了。对调用方来说结果一样：这个 id 取不到内容。"""
        seed.file(file_id="file_1", path="/definitely/not/here.mp4")

        assert client.get(f"{FILES}/preview/file_1").status_code == 404

    def test_preview_needs_a_token(self, anon_client: TestClient) -> None:
        """预览不是公开资源——它读的是用户的私有文件。"""
        assert anon_client.get(f"{FILES}/preview/file_1").status_code == 401

    def test_preview_does_not_collide_with_the_file_id_route(
        self, client: TestClient, seed: Any, tmp_path: Path
    ) -> None:
        """`preview` 是静态段，不能被 `/{file_id}` 当成一个 id 吃掉。

        两条路由都是 GET，注册顺序错了的话预览会返回一份 JSON 元数据。
        """
        _seed_real_file(seed, tmp_path, b"x")

        preview = client.get(f"{FILES}/preview/file_1")
        detail = client.get(f"{FILES}/file_1")

        assert preview.content == b"x"
        assert detail.json()["data"]["id"] == "file_1"


class TestFileDetail:
    """`GET /api/v1/library/files/{file_id}`。"""

    def test_returns_the_same_shape_as_the_list(
        self, client: TestClient, seed: Any
    ) -> None:
        """和列表项字段一致，调用方只需要一套解析逻辑。"""
        seed.file(file_id="file_1", name="report.pdf", media_type="document", size=2048)

        body = client.get(f"{FILES}/file_1").json()

        assert body["status"] == "success"
        detail = body["data"]
        assert detail["id"] == "file_1"
        assert detail["name"] == "report.pdf"
        # 类型字段是大驼峰 `FileType`，这是既有契约。
        assert detail["FileType"] == "document"
        # size 是纯数字字符串，不带单位——格式化是前端的事。
        assert detail["size"] == "2048"
        assert detail["parentFolder"] is None
        assert detail["path"]

    def test_reports_the_parent_folder(self, client: TestClient, seed: Any) -> None:
        seed.folder(folder_id="f_1", name="文档")
        seed.file(file_id="file_1", parent_folder="f_1")

        detail = client.get(f"{FILES}/file_1").json()["data"]

        assert detail["parentFolder"] == "f_1"

    def test_missing_file_is_404_envelope(self, client: TestClient) -> None:
        response = client.get(f"{FILES}/nope")

        assert response.status_code == 404
        body = response.json()
        assert body["status"] == "error"
        assert "nope" in body["error"]

    def test_detail_does_not_shadow_batch_delete(
        self, client: TestClient, seed: Any
    ) -> None:
        """`/batch-delete` 必须仍然是那个静态路由，不能被 `/{file_id}` 吃掉。

        两条都注册在同一个 router 上，FastAPI 按注册顺序匹配——顺序错了的话
        batch-delete 会被当成一个叫 "batch-delete" 的 file_id。
        """
        response = client.post(f"{FILES}/batch-delete", json={"file_ids": []})

        assert response.status_code == 200
        assert response.json()["status"] == "success"


class TestRecordAccess:
    """`POST /api/v1/library/files/{file_id}/access`。"""

    def test_recorded_access_shows_up_in_recent(
        self, client: TestClient, seed: Any
    ) -> None:
        """这条链路在新增之前是断的：recent 表没有任何写入口。"""
        seed.file(file_id="file_1")

        response = client.post(f"{FILES}/file_1/access")

        assert response.status_code == 200
        assert response.json() == {"status": "success", "data": None, "error": None}

        recent = client.get(RECENT).json()["data"]
        assert [item["file_id"] for item in recent] == ["file_1"]
        # 时间戳由服务端填，不接受调用方传入。
        assert recent[0]["accessed_at"]

    def test_repeated_access_is_recorded_each_time(
        self, client: TestClient, seed: Any
    ) -> None:
        """每次访问都是一条记录——这是访问历史，不是"去重后的文件集合"。"""
        seed.file(file_id="file_1")

        client.post(f"{FILES}/file_1/access")
        client.post(f"{FILES}/file_1/access")

        assert len(client.get(RECENT).json()["data"]) == 2

    def test_access_needs_a_token(self, anon_client: TestClient) -> None:
        assert anon_client.post(f"{FILES}/file_1/access").status_code == 401
