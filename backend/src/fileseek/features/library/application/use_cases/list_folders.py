from fileseek.features.library.application.dto import FolderDTO
from fileseek.features.library.application.mappers import folder_to_dto
from fileseek.features.library.application.queries import ListFoldersQuery
from fileseek.features.library.domain.repositories import FolderRepository


class ListFoldersUseCase:
    def __init__(self, folder_repo: FolderRepository) -> None:
        self.folder_repo = folder_repo

    async def execute(self, query: ListFoldersQuery) -> list[FolderDTO]:
        return [folder_to_dto(item) for item in await self.folder_repo.list_all()]
