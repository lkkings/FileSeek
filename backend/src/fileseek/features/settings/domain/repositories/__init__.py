from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from fileseek.features.settings.domain.entities import (
    ClassifierLabelSet,
    StorageLocation,
)


class StorageLocationRepository(Protocol):
    async def get_by_id(
        self,
        location_id: str,
        *,
        include_deleted: bool = False,
    ) -> StorageLocation | None: ...

    async def list_active_manageable(self) -> list[StorageLocation]: ...

    async def save(self, location: StorageLocation) -> StorageLocation: ...

    async def mark_deleted(self, location_id: str) -> bool: ...


class ClassifierLabelRepository(Protocol):
    async def get_label_set(self) -> ClassifierLabelSet: ...

    async def replace(self, labels: Sequence[str], category: str) -> None: ...

    async def replace_label_set(self, labels: ClassifierLabelSet) -> None: ...
