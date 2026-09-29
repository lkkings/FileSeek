from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from fileseek.features.search.application.queries import (
    FileSortBy,
    SearchFilesQuery,
)
from fileseek.features.search.application.use_cases import SearchFilesUseCase
from fileseek.shared.domain.file_types import FileCategory


@pytest.mark.asyncio
async def test_search_files_counts_with_request_filters() -> None:
    file_repo = AsyncMock()
    file_repo.query.return_value = []
    file_repo.count_by_category.return_value = {"document": 1}
    cache = AsyncMock()
    cache.get.return_value = None
    use_case = SearchFilesUseCase(AsyncMock(), AsyncMock(), file_repo, cache)
    request = SearchFilesQuery(
        query="",
        tag="travel",
        folder_id="folder-1",
        categories=[FileCategory.DOCUMENT],
        name_query="report",
        min_size_m=1,
        max_size_m=2,
        start_date="2026-09-01T00:00:00",
        end_date="2026-09-30T23:59:59",
        sort_by=FileSortBy.CREATED_AT,
    )

    result = await use_case.execute(request)

    expected_filters = {
        "name_query": "report",
        "tag": "travel",
        "min_size": 1_048_576,
        "max_size": 2_097_152,
        "start_date": "2026-09-01T00:00:00",
        "end_date": "2026-09-30T23:59:59",
        "folder_id": "folder-1",
        "categories": ["document"],
    }
    file_repo.count_by_category.assert_awaited_once_with(**expected_filters)
    assert result.counter == {"document": 1}
    assert result.total == 1
