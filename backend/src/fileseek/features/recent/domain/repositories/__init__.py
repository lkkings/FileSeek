from __future__ import annotations

from typing import Protocol

from fileseek.features.recent.domain.entities import RecentAccessRecord


class RecentAccessRepository(Protocol):
    """最近访问仓储接口。"""

    async def record_access(self, file_id: str, accessed_at: str) -> None: ...
    async def list_recent(self, limit: int) -> list[RecentAccessRecord]: ...
