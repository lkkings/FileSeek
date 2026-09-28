"""Library feature 仓储端口定义。

Domain 层定义 Protocol 接口，Infrastructure 层提供具体实现。
"""
from __future__ import annotations

from typing import Protocol,Sequence

from fileseek.features.library.domain.entities import File, Folder,FileChunk


class FileRepository(Protocol):
    """文件仓储接口。"""
    async def get_by_id(self, file_id: str) -> File | None: ...
    async def list_tags(self) -> list[str]: ...
    async def save(self, file: File) -> None: ...
    async def save_batch(self, files: Sequence[File]) -> None: ...
    async def delete(self, file_id: str) -> None: ...
    async def delete_batch(self, file_ids: list[str]) -> None: ...
    async def count_by_category(self) -> dict[str, int]: ...
    async def count(self) -> int: ...
    async def query(
        self,
        name_query: str | None = None,
        tag:str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        folder_id:str | None = None,
        categories:list[str] | None = None,
        page_number:int=1,
        page_size: int=20,
        sort_by: str | None = None,
        sort_order: str | None = None
    ) -> list[File]: ...

class FolderRepository(Protocol):
    """文件夹仓储接口。"""
    async def get_by_id(self, folder_id: str) -> Folder | None: ...
    async def get_by_name(self, name: str) -> Folder | None: ...
    async def list_all(self) -> list[Folder]: ...
    async def save(self, folder: Folder) -> None: ...
    async def delete(self, folder_id: str) -> None: ...
    async def increment_file_count(self, folder_id: str, delta: int) -> None: ...


class FileChunkRepository(Protocol):
    """文件分块仓储接口。"""
    async def save_batch(
        self,
        chunks: Sequence[FileChunk],
    ) -> None:
        """批量保存文件分块。"""
