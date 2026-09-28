from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from fileseek.features.library.application.use_cases import ListTagsUseCase
from fileseek.features.library.interfaces.http.dependencies import get_list_tags_use_case
from fileseek.shared.domain.exceptions import ApplicationError
from fileseek.shared.envelope import error_response, success_response

router = APIRouter(
    prefix="/tags",
)


@router.get("")
async def list_tags(
    use_case: Annotated[
        ListTagsUseCase,
        Depends(get_list_tags_use_case),
    ],
) -> dict[str, object]:
    """列出所有可用标签。"""
    try:
        tags = await use_case.execute()
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(tags)
