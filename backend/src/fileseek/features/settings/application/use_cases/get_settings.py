from fileseek.features.settings.application.dto import SettingsDTO
from fileseek.features.settings.application.mappers import settings_to_dto
from fileseek.features.settings.application.queries import GetSettingsQuery
from fileseek.features.settings.domain.repositories import SettingsRepository


class GetSettingsUseCase:
    def __init__(self, settings_repo: SettingsRepository) -> None:
        self.settings_repo = settings_repo

    async def execute(self, query: GetSettingsQuery) -> SettingsDTO:
        return settings_to_dto(await self.settings_repo.get_settings())
