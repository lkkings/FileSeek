from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RecentAccessRecord:
    """最近访问记录领域实体。"""

    file_id: str
    accessed_at: str
    id: int = field(default=0)

__all__ = ["RecentAccessRecord"]
