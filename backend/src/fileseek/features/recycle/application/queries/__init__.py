from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListRecycleItemsQuery:
    page: int
    page_size: int
