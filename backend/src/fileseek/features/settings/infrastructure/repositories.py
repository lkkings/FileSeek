"""Settings feature 的 Tortoise 仓储实现。"""

from fileseek.features.settings.domain.entities import NASConfig, Settings
from fileseek.infrastructure.database.models import SettingsModel

_SETTINGS_ROW_ID = "singleton"


class TortoiseSettingsRepository:
    def __init__(self, default_lib_root: str) -> None:
        self._default_lib_root = default_lib_root

    async def get_settings(self) -> Settings:
        return await self._get_settings()

    async def _get_settings(self) -> Settings:
        model = await SettingsModel.get_or_none(id=_SETTINGS_ROW_ID)
        if model is None:
            return Settings(lib_root=self._default_lib_root, nas_enabled=False)
        return Settings(lib_root=model.lib_root, nas_enabled=model.nas_enabled)

    async def save_settings(self, settings: Settings) -> None:
        await self._save_settings(settings)

    async def _save_settings(self, settings: Settings) -> None:
        await SettingsModel.update_or_create(id=_SETTINGS_ROW_ID, defaults={
            "lib_root": settings.lib_root, "nas_enabled": settings.nas_enabled,
        })

    async def get_nas_config(self) -> NASConfig | None:
        return await self._get_nas_config()

    async def _get_nas_config(self) -> NASConfig | None:
        model = await SettingsModel.get_or_none(id=_SETTINGS_ROW_ID)
        if model is None or model.nas_protocol is None:
            return None
        return NASConfig(protocol=model.nas_protocol, host=model.nas_host,
                         share_path=model.nas_share_path, username=model.nas_username,
                         password=model.nas_password)

    async def save_nas_config(self, config: NASConfig) -> None:
        await self._save_nas_config(config)

    async def _save_nas_config(self, config: NASConfig) -> None:
        await SettingsModel.update_or_create(id=_SETTINGS_ROW_ID, defaults={
            "lib_root": self._default_lib_root, "nas_enabled": True,
            "nas_protocol": config.protocol, "nas_host": config.host,
            "nas_share_path": config.share_path, "nas_username": config.username,
            "nas_password": config.password,
        })
