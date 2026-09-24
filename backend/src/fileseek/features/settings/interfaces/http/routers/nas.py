from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from fileseek.features.settings.application import (
    TestNASConnectionUseCase,
)
from fileseek.features.settings.interfaces.http.mappers import (
    nas_request_to_command,
    nas_result_to_dict,
)
from fileseek.features.settings.interfaces.http.dependencies import (
    get_test_nas_connection_use_case,
)
from fileseek.features.settings.interfaces.http.schemas import (
    NASTestRequest,
)
from fileseek.shared.envelope import (
    error_response,
    success_response,
)

router = APIRouter(
    prefix="/settings/nas",
    tags=["settings"],
)


@router.post("/test")
async def test_nas_connection(
    body: NASTestRequest,
    use_case: Annotated[
        TestNASConnectionUseCase,
        Depends(get_test_nas_connection_use_case),
    ],
) -> dict[str, object]:
    """测试 NAS 网络凭据连通性。"""
    # `TestNASConnectionUseCase.execute` 是同步的（它只做一次 TCP connect），
    # await 一个 dataclass 会抛 TypeError。
    message = use_case.execute(nas_request_to_command(body))

    return success_response(nas_result_to_dict(message))
