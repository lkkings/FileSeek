from __future__ import annotations

from fileseek.features.settings.application.commands import (
    TestNASConnectionCommand,
    UpdateSettingsCommand,
)
from fileseek.features.settings.application.dto import NASConnectionResultDTO, SettingsDTO
from fileseek.features.settings.interfaces.http.schemas import (
    NASTestRequest,
    SettingsResponse,
    SettingsUpdateRequest,
)


def update_settings_request_to_command(body: SettingsUpdateRequest) -> UpdateSettingsCommand:
    return UpdateSettingsCommand(lib_root=body.lib_root)


def nas_request_to_command(body: NASTestRequest) -> TestNASConnectionCommand:
    return TestNASConnectionCommand(**body.model_dump())


def settings_to_schema(value: SettingsDTO) -> SettingsResponse:
    return SettingsResponse(lib_root=value.lib_root, nas_enabled=value.nas_enabled)


def nas_result_to_dict(value: NASConnectionResultDTO) -> str:
    return value.message
