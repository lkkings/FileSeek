"""Library feature 仓储端口定义。

Domain 层定义 Protocol 接口，Infrastructure 层提供具体实现。
"""

from __future__ import annotations

from typing import Protocol

from fileseek.features.library.domain.entities import File, Folder, RecentAccessRecord, RecycleItem


class FileRepository(Protocol):
    """文件仓储接口。"""

    async def get_by_id(self, file_id: str) -> File | None: ...

    async def list_by_folder(
        self,
        folder_id: str | None,
        file_type: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[File], int]: ...

    async def save(self, file: File) -> None: ...

    async def delete(self, file_id: str) -> None: ...

    async def delete_batch(self, file_ids: list[str]) -> None: ...

    async def exists_by_path(self, path: str) -> bool: ...

    async def get_batch(self, file_ids: list[str]) -> dict[str, File]: ...

    async def get_filtered_files(
        self,
        name_query: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[File]: ...

class FolderRepository(Protocol):
    """文件夹仓储接口。"""

    async def get_by_id(self, folder_id: str) -> Folder | None: ...

    async def get_by_name(self, name: str) -> Folder | None: ...

    async def list_all(self) -> list[Folder]: ...

    async def save(self, folder: Folder) -> None: ...

    async def delete(self, folder_id: str) -> None: ...

    async def increment_file_count(self, folder_id: str, delta: int) -> None: ...

class RecentAccessRepository(Protocol):
    """最近访问仓储接口。"""

    async def record_access(self, file_id: str, accessed_at: str) -> None: ...

    async def list_recent(self, limit: int) -> list[RecentAccessRecord]: ...


class RecycleRepository(Protocol):
    """回收站仓储接口。"""

    async def get_by_id(self, item_id: str) -> RecycleItem | None: ...

    async def list_all(self, page: int, page_size: int) -> tuple[list[RecycleItem], int]: ...

    async def list_all_items(self) -> list[RecycleItem]: ...

    async def save(self, item: RecycleItem) -> None: ...

    async def delete(self, item_id: str) -> None: ...

    async def delete_all(self) -> None: ...
