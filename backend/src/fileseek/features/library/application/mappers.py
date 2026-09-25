from fileseek.features.library.application.dto import FileDTO, FolderDTO
from fileseek.features.library.domain.entities import File, Folder


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
        value.tags,
    )
