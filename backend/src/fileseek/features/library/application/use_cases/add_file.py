from hashlib import sha256
from pathlib import Path
from shutil import copyfileobj
from tempfile import gettempdir

from fileseek.config.settings import get_settings
from fileseek.features.library.application.commands import AddFileCommand
from fileseek.features.library.application.dto import AddFileResult
from fileseek.features.library.application.ports import FileSourcePort
from fileseek.features.library.domain.entities import File
from fileseek.features.library.domain.repositories import FileRepository, FolderRepository
from fileseek.features.tasks.domain.entities import Task
from fileseek.features.tasks.domain.ports import ClassifierLabelProvider, TaskManager
from fileseek.shared.domain.exceptions import (
    FileAlreadyExistsError,
    FileNotSupportError,
    NotFoundError,
)
from fileseek.shared.domain.identifiers import generate_id
from fileseek.shared.utils.file_utils import detect_file_type_from_file


class AddFileUseCase:
    def __init__(
        self,
        file_repo: FileRepository,
        folder_repo: FolderRepository,
        task_manager: TaskManager,
        source: FileSourcePort,
        label_provider: ClassifierLabelProvider,
    ) -> None:
        self.file_repo = file_repo
        self.folder_repo = folder_repo
        self.task_manager = task_manager
        self.source = source
        self.label_provider = label_provider
        self.settings = get_settings()

    async def execute(
        self,
        command: AddFileCommand,
    ) -> AddFileResult:
        if command.folder_id and  await self.folder_repo.get_by_id(command.folder_id) is None:
            raise NotFoundError(
                f"文件夹不存在: {command.folder_id}"
            )
        # 解析源文件路径
        metadata = await self.source.read_metadata(
            command.storage_id,
            command.path,
        )
        source_file = await self.source.resolve(
            command.storage_id,
            command.path,
        )
        # 获取文件类型
        digest = sha256()
        with source_file.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        file_id = digest.hexdigest()

        if await self.file_repo.get_by_id(file_id) is not None:
            raise FileAlreadyExistsError(f"文件已经存在：{command.path}")

        temp_root = self.settings.temp_dir or Path(gettempdir())
        temp_path = temp_root / file_id
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with source_file.open("rb") as source, temp_path.open("wb") as target:
                copyfileobj(source, target)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        file_type = detect_file_type_from_file(temp_path)
        if file_type is None or not file_type.is_support:
            temp_path.unlink(missing_ok=True)
            raise FileNotSupportError(f"不支持的文件类型: {command.path}")

        file = File(
            id=file_id,
            name=Path(command.path).name,
            file_type=file_type,
            category=file_type.category,
            size=metadata.size,
            modified=metadata.modified,
            path=command.path,
            folder_id=command.folder_id,
            storage_id=command.storage_id,
            access_state="available",
            tags=[],
        )
        await self.file_repo.save(file)
        await self.folder_repo.increment_file_count(
            command.folder_id,
            1,
        )
        label_snapshot = await self.label_provider.get_snapshot()
        task_id = generate_id("t")
        task = Task(
            id=task_id,
            file=file,
            metadata={
                "temp_path": str(temp_path),
                **label_snapshot.as_metadata(),
            }
        )
        await self.task_manager.create(task)
        return AddFileResult(file_id=file_id, task_id=task_id)
