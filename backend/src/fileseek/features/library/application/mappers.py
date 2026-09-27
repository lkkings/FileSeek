from fileseek.features.library.application.dto import FileDTO, FolderDTO
from fileseek.features.library.domain.entities import File, Folder
from datetime import datetime


def folder_to_dto(value: Folder) -> FolderDTO:
    modified_str = value.modified.isoformat() if isinstance(value.modified, datetime) else str(value.modified)
    return FolderDTO(
        id=value.id,
        name=value.name,
        icon_type=value.icon_type,
        description=value.description,
        modified=modified_str,
        file_count=value.file_count,
    )

def file_to_dto(value: File) -> FileDTO:
    modified_str = value.modified.isoformat() if isinstance(value.modified, datetime) else str(value.modified)
    return FileDTO(
        id=value.id,
        name=value.name,
        file_type=value.file_type.value if hasattr(value.file_type, "value") else str(value.file_type),
        category=value.category.value if hasattr(value.category, "value") else str(value.category),
        size=value.size,
        modified=modified_str,
        path=value.path,
        folder_id=value.folder_id,
        tags=value.tags,
    )
