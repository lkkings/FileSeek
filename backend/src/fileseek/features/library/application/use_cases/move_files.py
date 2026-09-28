from fileseek.features.library.application.commands import MoveFilesCommand
from fileseek.features.library.domain.exceptions import FileNotFoundError, FolderNotFoundError
from fileseek.features.library.domain.repositories import FileRepository, FolderRepository
from fileseek.shared.domain.exceptions import ValidationError


class MoveFilesUseCase:
    def __init__(
        self,
        file_repo: FileRepository,
        folder_repo: FolderRepository,
    ) -> None:
        self.file_repo = file_repo
        self.folder_repo = folder_repo

    async def execute(self, command: MoveFilesCommand) -> int:
        file_ids = list(dict.fromkeys(command.file_ids))
        if not file_ids:
            raise ValidationError("至少选择一个文件")

        target_folder = await self.folder_repo.get_by_id(command.target_folder_id)
        if target_folder is None:
            raise FolderNotFoundError(f"文件夹 {command.target_folder_id} 不存在")

        files = []
        for file_id in file_ids:
            file = await self.file_repo.get_by_id(file_id)
            if file is None:
                raise FileNotFoundError(f"文件 {file_id} 不存在")
            files.append(file)

        source_counts: dict[str | None, int] = {}
        for file in files:
            source_counts[file.folder_id] = source_counts.get(file.folder_id, 0) + 1
            file.move_to_folder(command.target_folder_id)

        await self.file_repo.save_batch(files)
        for source_folder_id, count in source_counts.items():
            if source_folder_id is not None:
                await self.folder_repo.increment_file_count(source_folder_id, -count)
        await self.folder_repo.increment_file_count(command.target_folder_id, len(files))

        return len(files)
