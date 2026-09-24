from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from fileseek.features.library.application.use_cases import (
    ClearRecycleBinUseCase,
    DeleteRecycleUseCase,
    ListRecycleItemsUseCase,
    RestoreRecycleUseCase,
)
from fileseek.features.library.application.commands import ClearRecycleBinCommand
from fileseek.features.library.interfaces.http.dependencies import (
    get_clear_recycle_bin_use_case,
    get_delete_recycle_use_case,
    get_list_recycle_items_use_case,
    get_restore_recycle_use_case,
)
from fileseek.features.library.interfaces.http.mappers import (
    delete_permanently_command,
    list_recycle_query,
    recycle_item_to_schema,
    restore_item_command,
)
from fileseek.shared.envelope import (
    error_response,
    success_response,
)
from fileseek.shared.application.exceptions import ApplicationError

router = APIRouter(
    prefix="/library/recycle",
    tags=["library"],
)


@router.get("")
async def list_recycle_items(
    use_case: Annotated[
        ListRecycleItemsUseCase,
        Depends(get_list_recycle_items_use_case),
    ],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    """列出回收站内容。"""
    items, total = await use_case.execute(list_recycle_query(page, page_size))

    return success_response(
        [recycle_item_to_schema(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        has_more=page * page_size < total,
    )


@router.post("/{item_id}/restore")
async def restore_recycle_item(
    item_id: str,
    use_case: Annotated[
        RestoreRecycleUseCase,
        Depends(get_restore_recycle_use_case),
    ],
) -> dict[str, object]:
    """从回收站还原文件。"""
    try:
        await use_case.execute(restore_item_command(item_id))
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(None)


@router.delete("/{item_id}")
async def delete_recycle_item(
    item_id: str,
    use_case: Annotated[
        DeleteRecycleUseCase,
        Depends(get_delete_recycle_use_case),
    ],
) -> dict[str, object]:
    """永久删除回收站条目。"""
    try:
        await use_case.execute(delete_permanently_command(item_id))
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(None)


@router.delete("")
async def clear_recycle_bin(
    use_case: Annotated[
        ClearRecycleBinUseCase,
        Depends(get_clear_recycle_bin_use_case),
    ],
) -> dict[str, object]:
    """清空回收站。"""
    await use_case.execute(ClearRecycleBinCommand())

    return success_response(None)
