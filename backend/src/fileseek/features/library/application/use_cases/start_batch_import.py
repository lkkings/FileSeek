from __future__ import annotations

from fileseek.features.library.application.commands import BatchImportCommand
from fileseek.features.library.application.dto import BatchImportStartedDTO
from fileseek.features.library.application.use_cases.batch_import import (
    BatchImportSessionManager,
)
from fileseek.features.library.domain.repositories import FolderRepository
from fileseek.shared.domain.exceptions import NotFoundError, ValidationError


class StartBatchImportUseCase:
    def __init__(
        self,
        folder_repository: FolderRepository,
        session_manager: BatchImportSessionManager,
    ) -> None:
        self.folder_repository = folder_repository
        self.session_manager = session_manager

    async def execute(
        self,
        command: BatchImportCommand,
    ) -> BatchImportStartedDTO:
        if not command.items:
            raise ValidationError("导入文件列表不能为空")
        if not command.folder_id:
            raise ValidationError("目标文件夹不能为空")
        if await self.folder_repository.get_by_id(command.folder_id) is None:
            raise NotFoundError(f"文件夹不存在: {command.folder_id}")

        return await self.session_manager.start(command)
