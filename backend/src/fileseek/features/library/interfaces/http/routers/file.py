from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response

from fileseek.features.library.application.use_cases import (
    AddFileUseCase,
    GetFileUseCase
)
from fileseek.features.library.interfaces.http.dependencies import (
    get_add_file_use_case,
    get_get_file_use_case
)
from fileseek.features.library.interfaces.http.mappers import (
    add_file_request_to_command,
    get_file_query,
)
from fileseek.features.library.interfaces.http.responses import stream_file
from fileseek.features.library.interfaces.http.schemas import (
    FileImportRequest,
    FileImportResponse,
)
from fileseek.shared.envelope import success_response

router = APIRouter(
    prefix="/files",
)


@router.post("")
async def add_file(
    body: FileImportRequest,
    use_case: Annotated[
        AddFileUseCase,
        Depends(get_add_file_use_case),
    ],
) -> dict[str, object]:
    """入库单个文件，返回生成的 file_id。"""
    file_id = await use_case.execute(add_file_request_to_command(body))
    return success_response(FileImportResponse(file_id=file_id).model_dump(by_alias=True))


@router.get("/preview/{file_id}")
async def preview_file(
    file_id: str,
    use_case: Annotated[
        GetFileUseCase,
        Depends(get_get_file_use_case),
    ],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> Response:
    """返回文件的原始字节，供预览/播放使用。

    这是唯一不走 envelope 的库路由：返回的是可被 `<img>` / `<video>` 直接解码的字节。
    支持 `Range`，播放器据此 seek（见 `routers/content.py`）。

    文件不存在或内容不可访问时用例抛 `NotFoundError`，由全局处理器转成 404 + envelope。
    """
    file = await use_case.execute(get_file_query(file_id))
    return stream_file(file.path, range_header)