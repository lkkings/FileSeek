"""Library feature 仓储端口定义。

Domain 层定义 Protocol 接口，Infrastructure 层提供具体实现。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from fileseek.features.library.domain.entities import (
    File,
    FileChunk,
    Folder,
    FolderSourceBinding,
    FolderSourceSeen,
)


class FileRepository(Protocol):
    """文件仓储接口。"""

    async def get_by_id(self, file_id: str) -> File | None: ...
    async def list_tags(self) -> list[str]: ...
    async def save(self, file: File) -> None: ...
    async def save_batch(self, files: Sequence[File]) -> None: ...
    async def delete(self, file_id: str) -> None: ...
    async def set_access_state(
        self,
        file_id: str,
        access_state: str,
    ) -> bool: ...
    async def delete_batch(self, file_ids: list[str]) -> None: ...
    async def count_by_category(
        self,
        *,
        name_query: str | None = None,
        tag: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        folder_id: str | None = None,
        categories: list[str] | None = None,
    ) -> dict[str, int]: ...
    async def count(
        self,
        *,
        name_query: str | None = None,
        tag: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        folder_id: str | None = None,
        categories: list[str] | None = None,
    ) -> int: ...
    async def query(
        self,
        name_query: str | None = None,
        tag: str | None = None,
        min_size: float | None = None,
        max_size: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        folder_id: str | None = None,
        categories: list[str] | None = None,
        page_number: int = 1,
        page_size: int = 20,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> list[File]: ...


class FolderRepository(Protocol):
    """文件夹仓储接口。"""

    async def get_by_id(self, folder_id: str) -> Folder | None: ...
    async def get_by_name(self, name: str) -> Folder | None: ...
    async def list_all(self) -> list[Folder]: ...
    async def save(self, folder: Folder) -> None: ...
    async def delete(self, folder_id: str) -> None: ...


class FolderSourceBindingRepository(Protocol):
    """Folder source binding repository interface."""

    async def get_by_id(self, binding_id: str) -> FolderSourceBinding | None: ...
    async def list_by_folder(self, folder_id: str) -> list[FolderSourceBinding]: ...
    async def list_enabled(self) -> list[FolderSourceBinding]: ...
    async def list_all(self) -> list[FolderSourceBinding]: ...
    async def save(self, binding: FolderSourceBinding) -> None: ...
    async def delete(self, binding_id: str) -> None: ...


class FolderSourceSeenRepository(Protocol):
    """Folder source seen-state repository interface."""

    async def list_paths(self, binding_id: str) -> set[str]: ...
    async def save(self, seen: FolderSourceSeen) -> None: ...
    async def delete_path(self, binding_id: str, source_path: str) -> None: ...
    async def replace_paths(
        self,
        binding_id: str,
        source_paths: Iterable[str],
    ) -> None: ...


class FileChunkRepository(Protocol):
    """文件分块仓储接口。"""

    async def save_batch(
        self,
        chunks: Sequence[FileChunk],
    ) -> None:
        """批量保存文件分块。"""

    async def get_chunks_by_range(
        self,
        file_id: str,
        page: int | None = None,
        chunk_start: int | None = None,
        chunk_end: int | None = None,
    ) -> list[FileChunk]:
        """按范围查询文件 chunks。

        Args:
            file_id: 文件 ID
            page: 可选，过滤到指定页
            chunk_start: 可选，基于 line_number（段落编号）的起始
            chunk_end: 可选，基于 line_number（段落编号）的结束

        Returns:
            匹配的 chunks 列表
        """
