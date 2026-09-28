from __future__ import annotations

from typing import Protocol

from fileseek.features.settings.application.dto import StorageDirectoryDTO
from fileseek.features.settings.domain.entities import StorageLocation


class StorageDirectoryBrowser(Protocol):
    async def list_entries(
        self,
        location: StorageLocation,
        path: str,
    ) -> StorageDirectoryDTO: ...
