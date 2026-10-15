from __future__ import annotations

from typing import Protocol


class StorageChangeCoordinator(Protocol):
    async def reconcile(self) -> None: ...
