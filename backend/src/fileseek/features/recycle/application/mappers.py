from fileseek.features.recycle.application.dto import RecycleItemDTO
from fileseek.features.recycle.domain.entities import RecycleItem


def recycle_item_to_dto(value: RecycleItem) -> RecycleItemDTO:
    return RecycleItemDTO(
        value.id,
        value.original_file_id,
        value.original_name,
        value.original_path,
        value.deleted_at,
        value.file_type.value,
        value.size,
    )
