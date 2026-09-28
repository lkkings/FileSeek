from fileseek.features.library.domain.repositories import FileRepository


class ListTagsUseCase:
    def __init__(self, file_repo: FileRepository) -> None:
        self.file_repo = file_repo

    async def execute(self) -> list[str]:
        return await self.file_repo.list_tags()
