from datetime import UTC, datetime

from fileseek.features.library.domain.entities import Folder
from fileseek.features.library.domain.repositories import FolderRepository
from fileseek.features.library.application.commands import CreateFolderCommand
from fileseek.features.library.application.dto import FolderDTO
from fileseek.features.library.application.mappers import folder_to_dto
from fileseek.shared.domain.identifiers import generate_id


class CreateFolderUseCase:
    def __init__(self, folder_repo: FolderRepository) -> None:
        self.folder_repo = folder_repo

    async def execute(
        self,
        command: CreateFolderCommand,
    ) -> FolderDTO:
        name, icon_type, description = command.name, command.icon_type, command.description
        folder = Folder(
            id=generate_id("d"),
            name=name,
            icon_type=icon_type,
            description=description,
            modified=datetime.now(UTC).isoformat(),
            file_count=0,
        )
        await self.folder_repo.save(folder)
        return folder_to_dto(folder)
