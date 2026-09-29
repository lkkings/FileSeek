from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from fileseek.config.constant import QUERY_CACHE_KEY
from fileseek.config.settings import get_settings
from fileseek.features.library.application.ports import FileSourcePort
from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.features.library.domain.repositories import FileRepository
from fileseek.features.recycle.application.commands import AddFiles2RecycleCommand
from fileseek.features.recycle.domain.entities import RecycleItem
from fileseek.features.recycle.domain.repositories import RecycleRepository
from fileseek.shared.domain.identifiers import generate_id
from fileseek.shared.utils.cache import TTLLRUCache


class AddFiles2RecycleUseCase:
    def __init__(
        self,
        file_repo: FileRepository,
        recycle_repo: RecycleRepository,
        search_cache: TTLLRUCache[str, Any],
        source_resolver: FileSourcePort,
    ) -> None:
        self.file_repo = file_repo
        self.recycle_repo = recycle_repo
        self.search_cache = search_cache
        self.setting = get_settings()
        self.source_resolver = source_resolver

    async def execute(self, command: AddFiles2RecycleCommand) -> None:
        try:
            for file_id in command.file_ids:
                await self._add_file(file_id)
        finally:
            await self.search_cache.clear(QUERY_CACHE_KEY)

    async def _add_file(self, file_id: str) -> None:
        file = await self.file_repo.get_by_id(file_id)

        if file is None:
            return
        if file.storage_id is None:
            raise SourceUnavailableError(f"文件缺少存储位置: {file_id}")

        source_file = await self.source_resolver.resolve(file.storage_id, file.path)
        if not source_file.exists() or not source_file.is_file():
            raise SourceUnavailableError(f"来源文件不可访问: {file.path}")

        # 移入回收站就是把文件压起来：`compress()` 压完会删掉原件，原路径上只剩那个包。
        # 两个路径要分开记——`original_path` 是还原的目标（文件原来在哪），
        # `recycle_path` 是那个包现在在哪。混成一个字段的话，还原后库里记的路径会指向
        # 压缩包而不是文件。
        original_path = Path(file.path)
        recycle_root = self.setting.recycle_dir or self.setting.lib_root / ".recycle"
        recycle_path = recycle_root / f"{file_id}.zip"
        recycle_path.parent.mkdir(parents=True, exist_ok=True)
        with (
            ZipFile(recycle_path, "w", ZIP_DEFLATED) as archive, source_file.open("rb") as source,
            archive.open(original_path.name, "w") as target,
        ):
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        source_file.unlink()
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
            storage_id=file.storage_id,
        )

        await self.recycle_repo.save(recycle_item)
