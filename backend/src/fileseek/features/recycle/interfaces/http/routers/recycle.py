from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from fileseek.features.recycle.application.commands import ClearRecycleBinCommand
from fileseek.features.recycle.application.use_cases import (
    AddFiles2RecycleUseCase,
    ClearRecycleBinUseCase,
    DeleteRecycleUseCase,
    ListRecycleItemsUseCase,
    RestoreRecycleUseCase,
)
from fileseek.features.recycle.interfaces.http.dependencies import (
    get_add_files2recycle_use_case,
    get_clear_recycle_bin_use_case,
    get_delete_recycle_use_case,
    get_list_recycle_items_use_case,
    get_restore_recycle_use_case,
)
from fileseek.features.recycle.interfaces.http.mappers import (
    add_files2recycle_command,
    delete_permanently_command,
    list_recycle_items_query,
    recycle_item_page_to_response,
    restore_items_command,
)
from fileseek.features.recycle.interfaces.http.schemas.recycle import (
    AddFiles2RecycleRequest,
    DeleteRecycleRequest,
    RestoreRecycleRequest,
)
from fileseek.shared.domain.exceptions import ApplicationError
from fileseek.shared.envelope import (
    error_response,
    success_response,
)

router = APIRouter(prefix="/recycle")


@router.get("")
async def list_recycle_items(
    use_case: Annotated[
        ListRecycleItemsUseCase,
        Depends(get_list_recycle_items_use_case),
    ],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    """分页列出回收站内容。"""
    items, total = await use_case.execute(list_recycle_items_query(page, page_size))

    return success_response(recycle_item_page_to_response(items, total, page, page_size))


@router.post("")
async def add_files2recycle(
    request_body: AddFiles2RecycleRequest,
    use_case: Annotated[
        AddFiles2RecycleUseCase,
        Depends(get_add_files2recycle_use_case),
    ],
) -> dict[str, object]:
    """批量将文件移入回收站。"""
    await use_case.execute(add_files2recycle_command(request_body))
    return success_response(None)


@router.post("/restore")
async def restore_recycle_items(
    request_body: RestoreRecycleRequest,
    use_case: Annotated[
        RestoreRecycleUseCase,
        Depends(get_restore_recycle_use_case),
    ],
) -> dict[str, object]:
    """批量从回收站还原文件。"""
    try:
        await use_case.execute(restore_items_command(request_body))
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(None)


@router.delete("")
async def delete_recycle_items(
    request_body: DeleteRecycleRequest,
    use_case: Annotated[
        DeleteRecycleUseCase,
        Depends(get_delete_recycle_use_case),
    ],
) -> dict[str, object]:
    """批量永久删除回收站条目。"""
    try:
        await use_case.execute(delete_permanently_command(request_body))
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(None)


@router.delete("/all")
async def clear_recycle_bin(
    use_case: Annotated[
        ClearRecycleBinUseCase,
        Depends(get_clear_recycle_bin_use_case),
    ],
) -> dict[str, object]:
    """清空回收站。"""
    await use_case.execute(ClearRecycleBinCommand())

    return success_response(None)
