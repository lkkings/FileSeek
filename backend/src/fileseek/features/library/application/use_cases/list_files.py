from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.repositories import (
    FileRepository,
    FolderRepository,
)
from fileseek.features.library.application.queries import ListFilesQuery
from fileseek.features.library.application.dto import FileDTO
from fileseek.features.library.application.mappers import file_to_dto


class ListFilesUseCase:
    def __init__(
        self,
        file_repo: FileRepository,
        folder_repo: FolderRepository,
    ) -> None:
        self.file_repo = file_repo
        self.folder_repo = folder_repo

    async def execute(
        self,
        query: ListFilesQuery,
    ) -> tuple[list[FileDTO], int]:
        folder_name, file_type, page, page_size = (
            query.folder_name,
            query.file_type,
            query.page,
            query.page_size,
        )
        folder_id = None

        if folder_name:
            folder = await self.folder_repo.get_by_name(folder_name)

            if folder is None:
                return [], 0

            folder_id = folder.id

        files, total = await self.file_repo.list_by_folder(
            folder_id=folder_id,
            file_type=file_type,
            page=page,
            page_size=page_size,
        )
        return [file_to_dto(item) for item in files], total
