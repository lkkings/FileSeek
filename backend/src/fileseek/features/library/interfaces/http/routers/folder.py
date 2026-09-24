from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from fileseek.features.library.application.use_cases import (
    CreateFolderUseCase,
    DeleteFolderUseCase,
    ListFoldersUseCase,
    UpdateFolderUseCase,
)
from fileseek.features.library.interfaces.http.dependencies import (
    get_create_folder_use_case,
    get_delete_folder_use_case,
    get_list_folders_use_case,
    get_update_folder_use_case,
)
from fileseek.features.library.interfaces.http.mappers import (
    create_folder_request_to_command,
    delete_folder_command,
    folder_to_schema,
    list_folders_query,
    update_folder_request_to_command,
)
from fileseek.features.library.interfaces.http.schemas import (
    FolderCreateRequest,
    FolderUpdateRequest,
)
from fileseek.shared.envelope import (
    error_response,
    success_response,
)
from fileseek.shared.application.exceptions import ApplicationError

router = APIRouter(
    prefix="/library/folders",
    tags=["library"],
)


@router.get("")
async def list_folders(
    use_case: Annotated[
        ListFoldersUseCase,
        Depends(get_list_folders_use_case),
    ],
) -> dict[str, object]:
    """列出所有文件夹。"""
    folders = await use_case.execute(list_folders_query())

    return success_response(
        [folder_to_schema(folder) for folder in folders],
    )


@router.post("")
async def create_folder(
    body: FolderCreateRequest,
    use_case: Annotated[
        CreateFolderUseCase,
        Depends(get_create_folder_use_case),
    ],
) -> dict[str, object]:
    """创建新文件夹。"""
    folder = await use_case.execute(create_folder_request_to_command(body))

    return success_response(
        folder_to_schema(folder),
    )


@router.put("/{folder_id}")
async def update_folder(
    folder_id: str,
    body: FolderUpdateRequest,
    use_case: Annotated[
        UpdateFolderUseCase,
        Depends(get_update_folder_use_case),
    ],
) -> dict[str, object]:
    """更新文件夹。"""
    try:
        folder = await use_case.execute(update_folder_request_to_command(folder_id, body))
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(
        folder_to_schema(folder),
    )


@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: str,
    use_case: Annotated[
        DeleteFolderUseCase,
        Depends(get_delete_folder_use_case),
    ],
) -> dict[str, object]:
    """删除文件夹。"""
    try:
        await use_case.execute(delete_folder_command(folder_id))
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(None)
