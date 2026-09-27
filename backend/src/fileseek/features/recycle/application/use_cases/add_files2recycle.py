from datetime import UTC, datetime

from fileseek.config.settings import get_settings
from fileseek.features.recycle.application.commands import AddFiles2RecycleCommand
from fileseek.features.recycle.domain.entities import RecycleItem
from fileseek.features.library.domain.repositories import FileRepository, FolderRepository
from fileseek.features.recycle.domain.repositories import RecycleRepository
from fileseek.infrastructure.fs import VirtualPath
from fileseek.shared.domain.identifiers import generate_id


class AddFiles2RecycleUseCase:
    def __init__(
        self,
        file_repo: FileRepository,
        folder_repo: FolderRepository,
        recycle_repo: RecycleRepository,
    ) -> None:
        self.file_repo = file_repo
        self.folder_repo = folder_repo
        self.recycle_repo = recycle_repo
        self.setting = get_settings()

    async def execute(self, command: AddFiles2RecycleCommand) -> None:
        for file_id in command.file_ids:
            await self._add_file(file_id)

    async def _add_file(self, file_id: str) -> None:
        file = await self.file_repo.get_by_id(file_id)

        if file is None:
            return
        # 移入回收站就是把文件压起来：`compress()` 压完会删掉原件，原路径上只剩那个包。
        # 两个路径要分开记——`original_path` 是还原的目标（文件原来在哪），
        # `recycle_path` 是那个包现在在哪。混成一个字段的话，还原后库里记的路径会指向
        # 压缩包而不是文件。
        original_path = VirtualPath(file.path)
        recycle_path = self.setting.recycle_dir / f"{file_id}.zip"
        original_path.compress(target_path=recycle_path)
        recycle_item = RecycleItem(
            id=generate_id("r"),
            original_file_id=file_id,
            original_name=file.name,
            original_path=str(original_path),
            recycle_path=str(recycle_path),
            deleted_at=datetime.now(UTC).isoformat(),
            file_type=file.file_type,
            size=file.size,
            original_folder_id=file.folder_id,
        )

        await self.recycle_repo.save(recycle_item)

        if file.folder_id:
            await self.folder_repo.increment_file_count(
                file.folder_id,
                -1,
            )
