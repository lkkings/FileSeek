from fileseek.features.library.application.ports import FileSourcePort, SourceFile
from fileseek.features.library.application.queries import GetFileQuery
from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.features.library.domain.repositories import FileRepository
from fileseek.shared.domain.exceptions import NotFoundError


class GetFileSourceUseCase:
    def __init__(
        self,
        file_repository: FileRepository,
        source_resolver: FileSourcePort,
    ) -> None:
        self.file_repository = file_repository
        self.source_resolver = source_resolver

    async def execute(self, query: GetFileQuery) -> SourceFile:
        file = await self.file_repository.get_by_id(query.file_id)
        if file is None:
            raise NotFoundError(f"文件不存在: {query.file_id}")

        if file.access_state == "unavailable":
            raise SourceUnavailableError(f"文件来源不可获取: {file.id}")

        storage_id = file.storage_id or "local"
        source_available = False
        try:
            source = await self.source_resolver.resolve(storage_id, file.path)
            source_available = source.exists() and source.is_file()
        except SourceUnavailableError:
            await self.file_repository.set_access_state(file.id, "unavailable")
            raise
        if not source_available:
            await self.file_repository.set_access_state(file.id, "unavailable")
            raise SourceUnavailableError(f"文件来源不可获取: {file.id}")

        if file.access_state != "available":
            await self.file_repository.set_access_state(file.id, "available")
        return source
