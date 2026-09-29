from datetime import UTC, datetime

from fileseek.features.library.application.dto import FileAvailabilityDTO
from fileseek.features.library.application.ports import FileSourcePort
from fileseek.features.library.application.queries import CheckFileAvailabilityQuery
from fileseek.features.library.domain.exceptions import SourceUnavailableError
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

        try:
            source = await self.source_resolver.resolve(
                file.storage_id or "local",
                file.path,
            )
        except SourceUnavailableError:
            return FileAvailabilityDTO(
                id=file.id,
                access_state=file.access_state,
                last_checked_at=datetime.now(UTC).isoformat(),
            )

        access_state = "available" if source.is_file() else "unavailable"

        await self.file_repository.set_access_state(file.id, access_state)
        return FileAvailabilityDTO(
            id=file.id,
            access_state=access_state,
            last_checked_at=datetime.now(UTC).isoformat(),
        )
