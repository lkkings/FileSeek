from fileseek.features.library.application.dto import FileDTO
from fileseek.features.library.application.mappers import file_to_dto
from fileseek.features.library.application.queries import GetFileQuery
from fileseek.features.library.domain.repositories import FileRepository
from fileseek.shared.domain.exceptions import NotFoundError


class GetFileUseCase:
    """按 id 读一条文件记录。

    "最近访问"靠它把 `{file_id, accessed_at}` 补成可渲染的条目——`GET /library/recent`
    只返回这两个字段。
    """

    def __init__(self, file_repo: FileRepository) -> None:
        self.file_repo = file_repo

    async def execute(self, query: GetFileQuery) -> FileDTO:
        file = await self.file_repo.get_by_id(query.file_id)

        if file is None:
            raise NotFoundError(f"文件不存在: {query.file_id}")

        return file_to_dto(file)
