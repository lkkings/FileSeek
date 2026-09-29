from fileseek.features.library.application.ports import FileSourcePort, SourceFile
from fileseek.features.library.application.queries import GetFileQuery
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
        storage_id = file.storage_id or "local"
        return await self.source_resolver.resolve(storage_id, file.path)
