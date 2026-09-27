from fileseek.features.recycle.application.commands import (
    AddFiles2RecycleCommand,
    DeletePermanentlyCommand,
    RestoreItemsCommand,
)
from fileseek.features.recycle.application.dto import RecycleItemDTO
from fileseek.features.recycle.application.queries import ListRecycleItemsQuery
from fileseek.features.recycle.interfaces.http.schemas.recycle import (
    AddFiles2RecycleRequest,
    DeleteRecycleRequest,
    RecycleItemPageResponse,
    RecycleItemResponse,
    RestoreRecycleRequest,
)


def add_files2recycle_command(body: AddFiles2RecycleRequest) -> AddFiles2RecycleCommand:
    return AddFiles2RecycleCommand(body.file_ids)

def restore_items_command(body: RestoreRecycleRequest) -> RestoreItemsCommand:
    return RestoreItemsCommand(body.item_ids)

def delete_permanently_command(body: DeleteRecycleRequest) -> DeletePermanentlyCommand:
    return DeletePermanentlyCommand(body.item_ids)

def list_recycle_items_query(page: int, page_size: int) -> ListRecycleItemsQuery:
    return ListRecycleItemsQuery(page, page_size)

def recycle_item_to_schema(dto: RecycleItemDTO) -> RecycleItemResponse:
    return RecycleItemResponse(
        id=dto.id,
        original_file_id=dto.original_file_id,
        original_name=dto.original_name,
        original_path=dto.original_path,
        deleted_at=dto.deleted_at,
        file_type=dto.file_type,
        size=str(dto.size),
    )

def recycle_item_page_to_response(
    dtos: list[RecycleItemDTO],
    total: int,
    page: int,
    page_size: int,
) -> RecycleItemPageResponse:
    offset = (page - 1) * page_size
    has_more = offset + page_size < total
    return RecycleItemPageResponse(
        items=[recycle_item_to_schema(dto) for dto in dtos],
        page_number=page,
        page_size=page_size,
        total=total,
        has_more=has_more,
    )
