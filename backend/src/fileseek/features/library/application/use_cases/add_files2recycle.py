from datetime import UTC, datetime

from fileseek.features.library.domain.entities import RecycleItem
from fileseek.features.library.domain.repositories import (
    FileRepository,
    FolderRepository,
    RecycleRepository,
)
from fileseek.shared.domain.identifiers import generate_id
from fileseek.features.library.application.commands import AddFiles2RecycleCommand

from fileseek.infrastructure.fs import VirtualPath
from fileseek.config.settings import get_settings


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
        file_ids = command.file_ids
        for file_id in file_ids:
            file = await self.file_repo.get_by_id(file_id)

            if file is None:
                continue
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
                original_parent_folder=file.parent_folder,
            )

            await self.recycle_repo.save(recycle_item)
            await self.file_repo.delete(file_id)

            if file.parent_folder:
                await self.folder_repo.increment_file_count(
                    file.parent_folder,
                    -1,
                )
