from fileseek.features.settings.application.dto import SettingsDTO
from fileseek.features.settings.domain.entities import Settings


def settings_to_dto(value: Settings) -> SettingsDTO:
    return SettingsDTO(lib_root=value.lib_root, nas_enabled=value.nas_enabled)
