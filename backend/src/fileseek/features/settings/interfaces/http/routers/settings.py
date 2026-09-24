from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from fileseek.features.settings.application import (
    GetSettingsUseCase,
    UpdateSettingsUseCase,
)
from fileseek.features.settings.application.queries import GetSettingsQuery
from fileseek.features.settings.interfaces.http.dependencies import (
    get_get_settings_use_case,
    get_update_settings_use_case,
)
from fileseek.features.settings.interfaces.http.mappers import (
    settings_to_schema,
    update_settings_request_to_command,
)
from fileseek.features.settings.interfaces.http.schemas import (
    SettingsUpdateRequest,
)
from fileseek.shared.envelope import (
    error_response,
    success_response,
)

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
)


@router.get("")
async def get_settings(
    use_case: Annotated[
        GetSettingsUseCase,
        Depends(get_get_settings_use_case),
    ],
) -> dict[str, object]:
    """读取系统存储根路径与 NAS 状态。"""
    settings = await use_case.execute(GetSettingsQuery())

    return success_response(
        settings_to_schema(settings),
    )


@router.post("")
async def update_settings(
    body: SettingsUpdateRequest,
    use_case: Annotated[
        UpdateSettingsUseCase,
        Depends(get_update_settings_use_case),
    ],
) -> dict[str, object]:
    """修改存储根路径。"""
    settings = await use_case.execute(update_settings_request_to_command(body))

    return success_response(
        settings_to_schema(settings),
    )
