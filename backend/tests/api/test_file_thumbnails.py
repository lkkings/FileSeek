from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from fileseek.features.library.application.dto import FileThumbnailDTO
from fileseek.features.library.application.queries import GetFileThumbnailQuery
from fileseek.features.library.domain.exceptions import (
    FileNotFoundError,
    SourceUnavailableError,
    ThumbnailUnavailableError,
)
from fileseek.shared.domain.exceptions import ValidationError


def test_thumbnail_success(auth_client: TestClient, app):
    use_case = AsyncMock()
    use_case.execute.return_value = FileThumbnailDTO(
        id="file-1",
        size="detail",
        data=b"webp-bytes",
        source_size=120,
        source_modified="2026-09-28T08:00:00+00:00",
    )
    app.state.dependencies["get_file_thumbnail_use_case"] = use_case

    response = auth_client.get("/api/v1/library/files/file-1/thumbnail?size=detail")

    assert response.status_code == 200
    assert response.content == b"webp-bytes"
    assert response.headers["content-type"] == "image/webp"
    assert "private" in response.headers["cache-control"]
    assert response.headers["etag"].startswith('"')
    assert response.headers["content-disposition"] == "inline"
    assert response.headers["x-content-type-options"] == "nosniff"
    use_case.execute.assert_awaited_once_with(
        GetFileThumbnailQuery(file_id="file-1", size="detail")
    )


def test_thumbnail_unknown_file_returns_not_found(auth_client: TestClient, app):
    use_case = AsyncMock()
    use_case.execute.side_effect = FileNotFoundError("文件不存在: file-999")
    app.state.dependencies["get_file_thumbnail_use_case"] = use_case

    response = auth_client.get("/api/v1/library/files/file-999/thumbnail")

    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_thumbnail_invalid_category_returns_validation_error(auth_client: TestClient, app):
    use_case = AsyncMock()
    use_case.execute.side_effect = ValidationError("仅支持图片和视频生成缩略图")
    app.state.dependencies["get_file_thumbnail_use_case"] = use_case

    response = auth_client.get("/api/v1/library/files/file-1/thumbnail")

    assert response.status_code == 400
    assert response.json()["status"] == "error"


def test_thumbnail_inaccessible_source_returns_safe_error(auth_client: TestClient, app, tmp_path):
    use_case = AsyncMock()
    use_case.execute.side_effect = ThumbnailUnavailableError("缩略图源文件不可访问")
    app.state.dependencies["get_file_thumbnail_use_case"] = use_case

    response = auth_client.get("/api/v1/library/files/file-1/thumbnail")

    assert response.status_code == 400
    assert response.json()["error"] == "缩略图源文件不可访问"
    assert str(tmp_path) not in response.text


def test_thumbnail_unavailable_source_returns_410(
    auth_client: TestClient,
    app,
) -> None:
    use_case = AsyncMock()
    use_case.execute.side_effect = SourceUnavailableError(
        "文件来源不可获取: file-1"
    )
    app.state.dependencies["get_file_thumbnail_use_case"] = use_case

    response = auth_client.get("/api/v1/library/files/file-1/thumbnail")

    assert response.status_code == 410
    assert response.json()["status"] == "error"
