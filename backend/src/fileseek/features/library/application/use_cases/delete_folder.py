from fileseek.features.library.application.commands import DeleteFolderCommand
from fileseek.features.library.application.ports import FolderSourceWatcherCoordinator
from fileseek.features.library.domain.exceptions import FolderNotFoundError
from fileseek.features.library.domain.repositories import FolderRepository


class DeleteFolderUseCase:
    def __init__(
        self,
        folder_repo: FolderRepository,
        watcher: FolderSourceWatcherCoordinator | None = None,
    ) -> None:
        self.folder_repo = folder_repo
        self.watcher = watcher

    async def execute(self, command: DeleteFolderCommand | str) -> None:
        folder_id = command.folder_id if isinstance(command, DeleteFolderCommand) else command
        folder = await self.folder_repo.get_by_id(folder_id)

        if folder is None:
            raise FolderNotFoundError(f"文件夹 {folder_id} 不存在")

        folder.ensure_can_delete()

        await self.folder_repo.delete(folder_id)
        if self.watcher is not None:
            await self.watcher.reconcile()
