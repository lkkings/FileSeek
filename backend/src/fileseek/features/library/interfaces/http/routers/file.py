from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response

from fileseek.features.library.application.commands import RecordAccessCommand
from fileseek.features.library.application.use_cases import (
    AddFiles2RecycleUseCase,
    AddFileUseCase,
    GetFileUseCase,
    ListFilesUseCase,
    RecordAccessUseCase,
)
from fileseek.features.library.interfaces.http.dependencies import (
    get_add_file_use_case,
    get_add_files2recycle_use_case,
    get_get_file_use_case,
    get_list_files_use_case,
    get_record_access_use_case,
)
from fileseek.features.library.interfaces.http.mappers import (
    add_file_request_to_command,
    delete_files_command,
    file_to_schema,
    get_file_query,
    list_files_query,
)
from fileseek.features.library.interfaces.http.responses import stream_file
from fileseek.features.library.interfaces.http.schemas import (
    FileBatchDeleteRequest,
    FileImportRequest,
    FileImportResponse,
)
from fileseek.shared.envelope import success_response

router = APIRouter(
    prefix="/library/files",
    tags=["library"],
)


@router.get("")
async def list_files(
    use_case: Annotated[
        ListFilesUseCase,
        Depends(get_list_files_use_case),
    ],
    folder: str | None = Query(None),
    file_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    """列出文件（分页）。"""
    files, total = await use_case.execute(list_files_query(folder, file_type, page, page_size))

    return success_response(
        [file_to_schema(file) for file in files],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
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


@router.post("/batch-delete")
async def batch_delete_files(
    body: FileBatchDeleteRequest,
    use_case: Annotated[
        AddFiles2RecycleUseCase,
        Depends(get_add_files2recycle_use_case),
    ],
) -> dict[str, object]:
    """批量删除文件（移入回收站）。"""
    await use_case.execute(delete_files_command(body.file_ids))

    return success_response(None)


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


# 下面几条带路径参数的路由必须注册在 `/batch-delete`、`/preview/{id}` 这些静态段之后：
# FastAPI 按注册顺序匹配，`/{file_id}` 先注册的话会把它们当成一个 file_id 吃掉。
@router.post("/{file_id}/access")
async def record_file_access(
    file_id: str,
    use_case: Annotated[
        RecordAccessUseCase,
        Depends(get_record_access_use_case),
    ],
) -> dict[str, object]:
    """记录一次文件访问，供"最近访问"列表使用。

    访问时间由用例取服务端当下的时间，不接受调用方传入——客户端时钟不可信，
    而这个列表是按时间排序的。
    """
    await use_case.execute(RecordAccessCommand(file_id=file_id))

    return success_response(None)


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    use_case: Annotated[
        GetFileUseCase,
        Depends(get_get_file_use_case),
    ],
) -> dict[str, object]:
    """读取单个文件的详情。

    响应结构和 `GET /library/files` 列表里的元素完全一致，这样调用方只需要一套
    解析逻辑。"最近访问"就靠它把 `{file_id, accessed_at}` 补成可渲染的条目。
    """
    file = await use_case.execute(get_file_query(file_id))

    return success_response(file_to_schema(file))
