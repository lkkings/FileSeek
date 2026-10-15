from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from fileseek.features.library.application.ports import FolderSourceWatcherCoordinator
from fileseek.features.library.application.use_cases import (
    CreateFolderSourceBindingUseCase,
    CreateFolderUseCase,
    DeleteFolderSourceBindingUseCase,
    DeleteFolderUseCase,
    ListFolderSourceBindingsUseCase,
    ListFoldersUseCase,
    UpdateFolderSourceBindingUseCase,
    UpdateFolderUseCase,
)
from fileseek.features.library.interfaces.http.dependencies import (
    get_create_folder_source_binding_use_case,
    get_create_folder_use_case,
    get_delete_folder_source_binding_use_case,
    get_delete_folder_use_case,
    get_folder_source_watcher,
    get_list_folder_source_bindings_use_case,
    get_list_folders_use_case,
    get_update_folder_source_binding_use_case,
    get_update_folder_use_case,
)
from fileseek.features.library.interfaces.http.mappers import (
    create_folder_request_to_command,
    create_folder_source_binding_request_to_command,
    delete_folder_command,
    delete_folder_source_binding_command,
    folder_source_binding_to_schema,
    folder_to_schema,
    list_folders_query,
    update_folder_request_to_command,
    update_folder_source_binding_request_to_command,
)
from fileseek.features.library.interfaces.http.schemas import (
    FolderCreateRequest,
    FolderSourceBindingCreateRequest,
    FolderSourceBindingUpdateRequest,
    FolderUpdateRequest,
)
from fileseek.shared.domain.exceptions import ApplicationError
from fileseek.shared.envelope import (
    error_response,
    success_response,
)

router = APIRouter(
    prefix="/folders",
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


@router.get("/{folder_id}/source-bindings")
async def list_folder_source_bindings(
    folder_id: str,
    use_case: Annotated[
        ListFolderSourceBindingsUseCase,
        Depends(get_list_folder_source_bindings_use_case),
    ],
) -> dict[str, object]:
    """List source bindings for one library folder."""
    try:
        bindings = await use_case.execute(folder_id)
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response([folder_source_binding_to_schema(binding) for binding in bindings])


@router.post("/{folder_id}/source-bindings")
async def create_folder_source_binding(
    folder_id: str,
    body: FolderSourceBindingCreateRequest,
    use_case: Annotated[
        CreateFolderSourceBindingUseCase,
        Depends(get_create_folder_source_binding_use_case),
    ],
    watcher: Annotated[
        FolderSourceWatcherCoordinator,
        Depends(get_folder_source_watcher),
    ],
) -> dict[str, object]:
    """Bind a watchable storage directory to a library folder."""
    try:
        binding = await use_case.execute(
            create_folder_source_binding_request_to_command(folder_id, body)
        )
        await watcher.reload_binding(binding.id)
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(folder_source_binding_to_schema(binding))


@router.patch("/{folder_id}/source-bindings/{binding_id}")
async def update_folder_source_binding(
    folder_id: str,
    binding_id: str,
    body: FolderSourceBindingUpdateRequest,
    use_case: Annotated[
        UpdateFolderSourceBindingUseCase,
        Depends(get_update_folder_source_binding_use_case),
    ],
    watcher: Annotated[
        FolderSourceWatcherCoordinator,
        Depends(get_folder_source_watcher),
    ],
) -> dict[str, object]:
    """Update a folder source binding."""
    try:
        binding = await use_case.execute(
            update_folder_source_binding_request_to_command(
                folder_id,
                binding_id,
                body,
            )
        )
        await watcher.reload_binding(binding.id)
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(folder_source_binding_to_schema(binding))


@router.delete("/{folder_id}/source-bindings/{binding_id}")
async def delete_folder_source_binding(
    folder_id: str,
    binding_id: str,
    use_case: Annotated[
        DeleteFolderSourceBindingUseCase,
        Depends(get_delete_folder_source_binding_use_case),
    ],
    watcher: Annotated[
        FolderSourceWatcherCoordinator,
        Depends(get_folder_source_watcher),
    ],
) -> dict[str, object]:
    """Delete a folder source binding."""
    _ = folder_id
    try:
        await use_case.execute(delete_folder_source_binding_command(binding_id))
        await watcher.remove_binding(binding_id)
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(None)
