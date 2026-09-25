from fileseek.features.recycle.application.commands import (
    AddFiles2RecycleCommand,
    DeletePermanentlyCommand,
    RestoreItemCommand,
)
from fileseek.features.recycle.application.queries import ListRecycleItemsQuery
from fileseek.features.recycle.interfaces.http.schemas.recycle import DeleteRecycleRequest


def add_files2recycle_command(body: DeleteRecycleRequest) -> AddFiles2RecycleCommand:
    return AddFiles2RecycleCommand(body.file_ids)

def restore_item_command(item_id: str) -> RestoreItemCommand:
    return RestoreItemCommand(item_id)

def delete_permanently_command(item_id: str) -> DeletePermanentlyCommand:
    return DeletePermanentlyCommand(item_id)

def list_recycle_items_query(page: int, page_size: int) -> ListRecycleItemsQuery:
    return ListRecycleItemsQuery(page, page_size)
