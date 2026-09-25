from datetime import datetime
from pathlib import Path

from fileseek.config.settings import get_settings
from fileseek.features.library.application.commands import AddFileCommand
from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.repositories import FileRepository, FolderRepository
from fileseek.features.tasks.domain.entities import Task
from fileseek.features.tasks.domain.ports import TaskManager
from fileseek.infrastructure.fs import VirtualPath
from fileseek.shared.application.exceptions import (
    FileAlreadyExistsError,
    FileNotSupportError,
    NotFoundError,
)
from fileseek.shared.domain.file_types import FileType
from fileseek.shared.utils.file_utils import bytes_hash, detect_file_type_from_file


class AddFileUseCase:
    def __init__(
        self,
        file_repo: FileRepository,
        folder_repo: FolderRepository,
        task_manager:TaskManager
    ) -> None:
        self.file_repo = file_repo
        self.folder_repo = folder_repo
        self.task_manager = task_manager
        self.settings = get_settings()

    async def execute(
        self,
        command: AddFileCommand,
    ) -> str:
        # 解析源文件路径
        source_path = VirtualPath(command.path)

        if not source_path.exists():
            raise FileNotFoundError(
                f"文件不存在: {command.path}"
            )
        if command.folder_id and  await self.folder_repo.get_by_id(command.folder_id) is None:
            raise NotFoundError(
                f"文件夹不存在: {command.folder_id}"
            )
        # 获取文件类型
        data_bytes = source_path.read_bytes()
        file_id = bytes_hash(data_bytes)
        temp_path = self.settings.temp_dir / f"{file_id}"
        temp_path.parent.mkdir(exist_ok=True,parents=True)
        temp_path.write_bytes(data_bytes)
        file_type = detect_file_type_from_file(temp_path)
        if file_type is None:
            raise FileNotSupportError(
                f"不支持的文件类型: {command.path}"
            )

        file = await self.file_repo.get_by_id(file_id)
        if file is not None:
            raise FileAlreadyExistsError(f"文件已经存在：{file.path}")

        file_stat = source_path.stat()
        file_size = file_stat["size"]
        modified_ts = file_stat["mtime"]
        modified = datetime.fromtimestamp(
            modified_ts
        ).isoformat()
        # 确定文件存储目录
        target_dir = self._get_target_directory(file_type)

        # 按日期创建目录
        date_dir = target_dir / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        target_path = date_dir / Path(command.path).name
        if source_path.is_local():
            # 本地文件的就移动到库中，非本地只做记录和索引
            target_path.write_bytes(data_bytes)
            source_path.delete()
            target_path = VirtualPath(target_path)
        else:
            target_path = source_path
        # 创建领域对象
        file = File(
            id=file_id,
            name=target_path.name,
            file_type=file_type,
            size=file_size,
            modified=modified,
            path=str(target_path),
            parent_folder=command.folder_id,
            tags=[],
        )
        await self.file_repo.save(file)
        if command.folder_id:
            await self.folder_repo.increment_file_count(
                command.folder_id,
                1,
            )
        task = Task(
            id=file_id,
            source_path=str(temp_path),
            lib_path=str(target_path),
            file_type=file_type.value,
            file_modified_ts=modified_ts
        )
        await self.task_manager.create(task)
        return file_id

    def _get_target_directory(
        self,
        file_type: FileType,
    ) -> Path:
        if file_type.is_document:
            return self.settings.lib_root / "documents"

        if file_type.is_image:
            return self.settings.lib_root / "images"

        if file_type.is_video:
            return self.settings.lib_root / "videos"

        raise FileNotSupportError(
            f"不支持的文件类型: {file_type}"
        )
