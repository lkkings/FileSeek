from datetime import UTC, datetime

from fileseek.features.library.application.dto import FileAvailabilityDTO
from fileseek.features.library.application.ports import FileSourcePort
from fileseek.features.library.application.queries import CheckFileAvailabilityQuery
from fileseek.features.library.domain.repositories import FileRepository
from fileseek.shared.domain.exceptions import NotFoundError


class CheckFileAvailabilityUseCase:
    def __init__(
        self,
        file_repository: FileRepository,
        source_resolver: FileSourcePort,
    ) -> None:
        self.file_repository = file_repository
        self.source_resolver = source_resolver

    async def execute(
        self,
        query: CheckFileAvailabilityQuery,
    ) -> FileAvailabilityDTO:
        file = await self.file_repository.get_by_id(query.file_id)
        if file is None:
            raise NotFoundError(f"文件不存在: {query.file_id}")

        access_state = "unavailable"
        try:
            source = await self.source_resolver.resolve(
                file.storage_id or "local",
                file.path,
            )
            if source.exists() and source.is_file():
                access_state = "available"
        except Exception:
            access_state = "unavailable"

        await self.file_repository.set_access_state(file.id, access_state)
        return FileAvailabilityDTO(
            id=file.id,
            access_state=access_state,
            last_checked_at=datetime.now(UTC).isoformat(),
        )
