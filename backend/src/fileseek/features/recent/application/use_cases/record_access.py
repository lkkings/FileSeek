from datetime import UTC, datetime

from fileseek.features.recent.application.commands import RecordAccessCommand
from fileseek.features.recent.domain.repositories import RecentAccessRepository


class RecordAccessUseCase:
    def __init__(self, recent_repo: RecentAccessRepository) -> None:
        self.recent_repo = recent_repo

    async def execute(self, command: RecordAccessCommand) -> None:
        await self.recent_repo.record_access(
            file_id=command.file_id,
            accessed_at=datetime.now(UTC).isoformat(),
        )
