"""文件仓储读出来的 `modified` 必须是字符串。

`FileModel.modified` 是 `DatetimeField`，而 `File.modified`、`FileDTO.modified`、
`FileResponse.modified` 三层都是 `str`——响应契约里这个字段就是字符串。写入侧存的是 ISO 串
（`AddFileUseCase` 拿 `datetime.isoformat()`），SQLite 收得下，于是"写进去是串、读出来是
datetime"，一路无人拦截，直到 `GET /api/v1/library/files` 里 Pydantic 校验才抛
`ValidationError: modified Input should be a valid string`——整条列表接口 500。

四条读路径都要收口，所以这里逐条盯。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from tortoise import Tortoise

from fileseek.features.library.application.mappers import file_to_dto
from fileseek.features.library.infrastructure.repositories.file import FileRepositoryImpl
from fileseek.features.library.interfaces.http.mappers import file_to_schema
from fileseek.infrastructure.database.models import FileModel, FolderModel


@pytest_asyncio.fixture
async def db():
    """一个内存库。建表走真实模型，所以列类型和生产一致。

    `asyncio_mode = "strict"`（见 pyproject.toml）下 async fixture 必须用
    `pytest_asyncio.fixture`：用普通的 `pytest.fixture` 不会被 await，测试拿到的是一个
    async generator，Tortoise 根本没初始化，报错是 "default_connection ... cannot be None"。
    """
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["fileseek.infrastructure.database.models"]},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


async def _seed(file_id: str = "f_1", folder_id: str | None = None) -> None:
    """按写入侧的真实做法落一行：`modified` 是 ISO 串，不是 datetime 对象。"""
    if folder_id:
        await FolderModel.create(
            id=folder_id,
            name="工作",
            icon_type="work",
            description="",
            modified=datetime.now(UTC).isoformat(),
        )
    await FileModel.create(
        id=file_id,
        name=f"{file_id}.txt",
        file_type="document",
        size=7,
        modified=datetime.now(UTC).isoformat(),
        path=f"/lib/{file_id}.txt",
        parent_folder_id=folder_id,
    )


@pytest.mark.asyncio
async def test_the_column_really_does_hand_back_a_datetime(db: None) -> None:
    """先确认前提：这个列读出来确实是 datetime，否则下面几条测的就是空气。"""
    await _seed()

    model = await FileModel.get(id="f_1")

    assert isinstance(model.modified, datetime)


@pytest.mark.asyncio
async def test_get_by_id_returns_modified_as_a_string(db: None) -> None:
    await _seed()

    file = await FileRepositoryImpl().get_by_id("f_1")

    assert file is not None
    assert isinstance(file.modified, str)


@pytest.mark.asyncio
async def test_list_by_folder_returns_modified_as_a_string(db: None) -> None:
    await _seed(folder_id="d_1")

    files, total = await FileRepositoryImpl().list_by_folder(
        folder_id="d_1", file_type=None, page=1, page_size=20
    )

    # 这条就是用户碰到的那个 500：`GET /library/files` 走的是它。
    assert total == 1
    assert isinstance(files[0].modified, str)


@pytest.mark.asyncio
async def test_get_batch_returns_modified_as_a_string(db: None) -> None:
    await _seed("f_1")
    await _seed("f_2")

    found = await FileRepositoryImpl().get_batch(["f_1", "f_2"])

    assert {key: isinstance(value.modified, str) for key, value in found.items()} == {
        "f_1": True,
        "f_2": True,
    }


@pytest.mark.asyncio
async def test_get_filtered_files_returns_modified_as_a_string(db: None) -> None:
    await _seed()

    files = await FileRepositoryImpl().get_filtered_files(name_query="f_1")

    assert [isinstance(file.modified, str) for file in files] == [True]


@pytest.mark.asyncio
async def test_the_listed_file_reaches_the_response_schema(db: None) -> None:
    """走完 仓储 → DTO → FileResponse 整条链。

    用户看到的报错是在最后一步抛的，所以这里断言的是"构造得出来"，而不只是中间某层的类型。
    """
    await _seed(folder_id="d_1")

    files, _ = await FileRepositoryImpl().list_by_folder(
        folder_id="d_1", file_type=None, page=1, page_size=20
    )
    schema = file_to_schema(file_to_dto(files[0]))

    assert isinstance(schema.modified, str)
    # 能被 `datetime.fromisoformat` 认回去，前端才好格式化（`api/library.ts::formatModified`）。
    assert datetime.fromisoformat(schema.modified)


@pytest.mark.asyncio
async def test_a_string_column_would_still_pass_through(db: None) -> None:
    """列类型哪天改回 CharField 也不能坏。

    `_as_iso` 只在拿到 datetime 时转换，字符串原样返回——这样这个收口不依赖列类型。
    """
    from fileseek.features.library.infrastructure.repositories.file import _as_iso

    assert _as_iso("2026-09-23T19:03:46+00:00") == "2026-09-23T19:03:46+00:00"
    assert _as_iso(datetime(2026, 9, 23, 19, 3, 46, tzinfo=UTC)) == "2026-09-23T19:03:46+00:00"
