from __future__ import annotations
import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response, StreamingResponse

from fileseek.features.library.application.use_cases import (
    CheckFileAvailabilityUseCase,
    GetFileThumbnailUseCase,
    GetFileUseCase,
    GetFileSourceUseCase,
    MoveFilesUseCase,
    StartBatchImportUseCase,
)
from fileseek.features.library.application.dto import ImportEventDTO
from fileseek.features.library.application.use_cases.batch_import import (
    BatchImportSessionManager,
)
from fileseek.features.library.interfaces.http.dependencies import (
    get_batch_import_session_manager,
    get_check_file_availability_use_case,
    get_file_thumbnail_use_case,
    get_get_file_use_case,
    get_get_file_source_use_case,
    get_move_files_use_case,
    get_start_batch_import_use_case,
)
from fileseek.features.library.interfaces.http.mappers import (
    batch_import_request_to_command,
    get_file_query,
    get_file_thumbnail_query,
    check_file_availability_query,
    file_availability_to_schema,
    move_files_request_to_command,
)
from fileseek.features.library.interfaces.http.responses import stream_file, thumbnail_response
from fileseek.features.library.interfaces.http.schemas import (
    BatchImportRequest,
    BatchImportResponse,
    MoveFilesRequest,
    MoveFilesResponse,
)
from fileseek.shared.envelope import success_response

router = APIRouter(
    prefix="/files",
)


@router.post("/import")
async def start_batch_import(
    body: BatchImportRequest,
    use_case: Annotated[
        StartBatchImportUseCase,
        Depends(get_start_batch_import_use_case),
    ],
) -> dict[str, object]:
    """启动批量导入会话。"""
    started = await use_case.execute(batch_import_request_to_command(body))
    return success_response(
        BatchImportResponse(
            import_id=started.import_id,
            total=started.total,
        ).model_dump(by_alias=True)
    )


@router.get("/import/{import_id}/events")
async def stream_import_events(
    import_id: str,
    session_manager: Annotated[
        BatchImportSessionManager,
        Depends(get_batch_import_session_manager),
    ],
    last_event_id_header: Annotated[
        str | None,
        Header(alias="Last-Event-ID"),
    ] = None,
) -> StreamingResponse:
    """以 SSE 返回批量导入事件，支持 Last-Event-ID 重连。"""
    try:
        last_event_id = int(last_event_id_header or 0)
    except ValueError:
        last_event_id = 0

    async def stream() -> AsyncIterator[str]:
        iterator = session_manager.subscribe(import_id, last_event_id)
        while True:
            try:
                event = await asyncio.wait_for(anext(iterator), timeout=15)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            except StopAsyncIteration:
                break
            if event is None:
                break
            yield _format_event(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _format_event(event: ImportEventDTO) -> str:
    payload = json.dumps(event.payload, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.id}\nevent: {event.type}\ndata: {payload}\n\n"


@router.post("/move")
async def move_files(
    body: MoveFilesRequest,
    use_case: Annotated[
        MoveFilesUseCase,
        Depends(get_move_files_use_case),
    ],
) -> dict[str, object]:
    """批量移动文件到指定文件夹。"""
    moved_count = await use_case.execute(move_files_request_to_command(body))

    return success_response(
        MoveFilesResponse(moved_count=moved_count).model_dump(by_alias=True),
    )


@router.get("/preview/{file_id}")
async def preview_file(
    file_id: str,
    use_case: Annotated[
        GetFileSourceUseCase,
        Depends(get_get_file_source_use_case),
    ],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> Response:
    """返回文件的原始字节，供预览/播放使用。

    这是唯一不走 envelope 的库路由：返回的是可被 `<img>` / `<video>` 直接解码的字节。
    支持 `Range`。

    文件不存在或内容不可访问时用例抛 `NotFoundError`，由全局处理器转成 404 + envelope。
    """
    source = await use_case.execute(get_file_query(file_id))
    return stream_file(source, range_header)


@router.get("/{file_id}/thumbnail")
async def get_file_thumbnail(
    file_id: str,
    use_case: Annotated[
        GetFileThumbnailUseCase,
        Depends(get_file_thumbnail_use_case),
    ],
    size: Annotated[Literal["list", "detail"], Query()] = "list",
) -> Response:
    """Return a bounded WebP thumbnail for an image or video file."""

    thumbnail = await use_case.execute(get_file_thumbnail_query(file_id, size))
    return thumbnail_response(
        thumbnail.data,
        source_size=thumbnail.source_size,
        source_modified=thumbnail.source_modified,
    )


@router.post("/{file_id}/availability-check")
async def check_file_availability(
    file_id: str,
    use_case: Annotated[
        CheckFileAvailabilityUseCase,
        Depends(get_check_file_availability_use_case),
    ],
) -> dict[str, object]:
    result = await use_case.execute(check_file_availability_query(file_id))
    return success_response(file_availability_to_schema(result))
