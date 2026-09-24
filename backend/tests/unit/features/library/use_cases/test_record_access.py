"""Tests for RecordAccessUseCase."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fileseek.features.library.application.use_cases.record_access import RecordAccessUseCase
from fileseek.features.library.application.commands import RecordAccessCommand
from fileseek.features.library.domain.repositories import RecentAccessRepository


@pytest.mark.asyncio
async def test_record_access_success() -> None:
    recent_repo = AsyncMock(spec=RecentAccessRepository)
    use_case = RecordAccessUseCase(recent_repo)

    await use_case.execute(RecordAccessCommand("file_abc"))

    recent_repo.record_access.assert_awaited_once()
    args, kwargs = recent_repo.record_access.call_args
    assert kwargs["file_id"] == "file_abc"
    assert "accessed_at" in kwargs
