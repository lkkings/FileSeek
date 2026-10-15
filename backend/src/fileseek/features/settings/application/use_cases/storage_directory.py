from __future__ import annotations

from fileseek.features.settings.application.dto import StorageDirectoryDTO
from fileseek.features.settings.application.ports.storage_directory import (
    StorageDirectoryBrowser,
)
from fileseek.features.settings.application.queries import ListStorageDirectoryQuery
from fileseek.features.settings.domain.exceptions import (
    StorageBrowseUnavailableError,
    StorageBrowseUnsupportedError,
)
from fileseek.features.settings.domain.repositories import StorageLocationRepository
from fileseek.shared.domain.exceptions import NotFoundError


class ListStorageDirectoryUseCase:
    def __init__(
        self,
        repository: StorageLocationRepository,
        browser: StorageDirectoryBrowser,
    ) -> None:
        self.repository = repository
        self.browser = browser

    async def execute(
        self,
        query: ListStorageDirectoryQuery,
    ) -> StorageDirectoryDTO:
        location = await self.repository.get_by_id(
            query.storage_id,
            include_deleted=True,
        )
        if location is None:
            raise NotFoundError(f"存储位置不存在: {query.storage_id}")
        if not location.is_active:
            raise StorageBrowseUnavailableError(f"存储位置已删除: {location.id}")
        if location.type == "external" or location.protocol not in {"file", "mounted"}:
            raise StorageBrowseUnsupportedError(f"存储协议暂不支持目录浏览: {location.protocol}")

        return await self.browser.list_entries(location, query.path)
