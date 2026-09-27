from datetime import datetime
from pathlib import Path

from fileseek.config.settings import get_settings
from fileseek.features.library.application.commands import AddFileCommand
from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.repositories import FileRepository, FolderRepository
from fileseek.features.tasks.domain.entities import Task
from fileseek.features.tasks.domain.ports import TaskManager
from fileseek.infrastructure.fs import VirtualPath
from fileseek.shared.domain.exceptions import (
    FileAlreadyExistsError,
    FileNotSupportError,
    NotFoundError,
)
from fileseek.shared.domain.file_types import FileType
from fileseek.shared.utils.file_utils import bytes_hash, detect_file_type_from_file
from fileseek.shared.domain.identifiers import generate_id


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
        if file_type is None or not file_type.is_support:
            raise FileNotSupportError(
                f"不支持的文件类型: {command.path}"
            )

        file_obj = await self.file_repo.get_by_id(file_id)
        if file_obj is not None:
            raise FileAlreadyExistsError(f"文件已经存在：{file_obj.path}")

        file_stat = source_path.stat()
        file_size = file_stat["size"]
        modified_ts = file_stat["mtime"]
        modified = datetime.fromtimestamp(
            modified_ts
        )
        save_path = self._get_library_path(command.path,file_type)
        if source_path.is_local():
            # 本地文件的就移动到库中，非本地只做记录和索引
            save_path.write_bytes(data_bytes)
            save_path = VirtualPath(save_path)
        else:
            # 非本地文件就记录原始路径
            save_path = source_path
        # 创建领域对象
        file = File(
            id=file_id,
            name=save_path.name,
            file_type=file_type,
            category=file_type.category,
            size=file_size,
            modified=modified,
            path=str(save_path),
            folder_id=command.folder_id,
            tags=[],
        )
        await self.file_repo.save(file)
        await self.folder_repo.increment_file_count(
            command.folder_id,
            1,
        )
        task = Task(
            id=generate_id("t"),
            file=file,
            metadata={"temp_path": str(temp_path)}
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

    def _get_library_path(self,ori_path:str,file_type:FileType):
        # 确定文件存储目录
        target_dir = self._get_target_directory(file_type)
        # 按日期创建目录
        date_dir = target_dir / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        library_path = date_dir / Path(ori_path).name
        i = 1
        while True:
            if not library_path.exists():
                break
            library_path = date_dir / f"{library_path.stem}_{i}{library_path.suffix}"
            i += 1
        return library_path
