from __future__ import annotations

from fastapi import Request

from fileseek.features.settings.application import (
    GetSettingsUseCase,
    TestNASConnectionUseCase,
    UpdateSettingsUseCase,
)
from fileseek.shared.application.dependencies import resolve_dependency


def get_get_settings_use_case(request: Request) -> GetSettingsUseCase:
    return resolve_dependency(request, "get_settings_use_case")


def get_update_settings_use_case(request: Request) -> UpdateSettingsUseCase:
    return resolve_dependency(request, "update_settings_use_case")


def get_test_nas_connection_use_case(request: Request) -> TestNASConnectionUseCase:
    return resolve_dependency(request, "test_nas_connection_use_case")
