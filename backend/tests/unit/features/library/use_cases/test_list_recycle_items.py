"""Tests for ListRecycleItemsUseCase."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fileseek.features.library.application.use_cases.list_recycle_items import (
    ListRecycleItemsUseCase,
)
from fileseek.features.library.application.queries import ListRecycleItemsQuery
from fileseek.features.library.domain.entities import RecycleItem
from fileseek.features.library.domain.repositories import RecycleRepository
from fileseek.shared.domain.file_types import FileType


@pytest.mark.asyncio
async def test_list_recycle_items_success() -> None:
    recycle_repo = AsyncMock(spec=RecycleRepository)
    item1 = RecycleItem(
        id="r_1",
        original_file_id="file_1",
        original_name="old.txt",
        original_path="/old.txt",
        deleted_at="2026-01-01T00:00:00Z",
        file_type=FileType.DOCUMENT,
        size=10,
    )
    recycle_repo.list_all.return_value = ([item1], 1)

    use_case = ListRecycleItemsUseCase(recycle_repo)
    items, total = await use_case.execute(ListRecycleItemsQuery(1, 20))

    assert items[0].id == item1.id
    assert total == 1
    recycle_repo.list_all.assert_awaited_once_with(1, 20)
