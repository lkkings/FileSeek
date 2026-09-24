"""Settings feature 仓储端口定义。

Domain 层定义 Protocol 接口，Infrastructure 层提供具体实现。
"""

from __future__ import annotations

from typing import Protocol

from fileseek.features.settings.domain.entities import NASConfig, Settings


class SettingsRepository(Protocol):
    """设置仓储接口。"""

    async def get_settings(self) -> Settings: ...

    async def save_settings(self, settings: Settings) -> None: ...

    async def get_nas_config(self) -> NASConfig | None: ...

    async def save_nas_config(self, config: NASConfig) -> None: ...
