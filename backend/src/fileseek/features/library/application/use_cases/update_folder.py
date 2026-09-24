from fileseek.features.library.domain.entities import Folder
from fileseek.features.library.domain.exceptions import FolderNotFoundError
from fileseek.features.library.domain.repositories import FolderRepository
from fileseek.features.library.application.commands import UpdateFolderCommand
from fileseek.features.library.application.dto import FolderDTO
from fileseek.features.library.application.mappers import folder_to_dto


class UpdateFolderUseCase:
    def __init__(self, folder_repo: FolderRepository) -> None:
        self.folder_repo = folder_repo

    async def execute(
        self,
        command: UpdateFolderCommand,
    ) -> FolderDTO:
        folder_id, name, icon_type, description = (
            command.folder_id,
            command.name,
            command.icon_type,
            command.description,
        )
        folder = await self.folder_repo.get_by_id(folder_id)

        if folder is None:
            raise FolderNotFoundError(f"文件夹 {folder_id} 不存在")

        folder.rename(name)
        folder.change_icon_type(icon_type)
        folder.change_description(description)

        await self.folder_repo.save(folder)

        return folder_to_dto(folder)
