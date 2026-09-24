from fileseek.features.library.application.commands import DeleteFileCommand
from fileseek.features.library.domain.repositories import FileRepository

from fileseek.infrastructure.fs import VirtualPath


class DeleteFileUseCase:
    def __init__(
        self,
        file_repo: FileRepository,
    ) -> None:
        self.file_repo = file_repo

    async def execute(
        self,
        command: DeleteFileCommand,
    ) -> None:
        # 获取文件
        file = await self.file_repo.get_by_id(command.file_id)
        if file is None:
            return
        # 解析文件实际路径
        file_path = VirtualPath(file.path)
        # 删除实际文件
        if file_path.exists():
            file_path.delete()
        # 删除文件记录
        await self.file_repo.delete(command.file_id)