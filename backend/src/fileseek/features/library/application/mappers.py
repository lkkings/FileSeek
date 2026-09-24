from fileseek.features.library.application.dto import (
    FileDTO,
    FolderDTO,
    RecentAccessDTO,
    RecycleItemDTO,
)
from fileseek.features.library.domain.entities import File, Folder, RecentAccessRecord, RecycleItem


def folder_to_dto(value: Folder) -> FolderDTO:
    return FolderDTO(
        value.id, value.name, value.icon_type, value.description, value.modified, value.file_count
    )


def file_to_dto(value: File) -> FileDTO:
    return FileDTO(
        value.id,
        value.name,
        value.file_type.value,
        value.size,
        value.modified,
        value.path,
        value.parent_folder,
    )


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


def recent_access_to_dto(value: RecentAccessRecord) -> RecentAccessDTO:
    return RecentAccessDTO(value.file_id, value.accessed_at)

