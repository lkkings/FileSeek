from fastapi import Request

from fileseek.features.settings.application.use_cases import (
    CreateStorageLocationUseCase,
    DeleteStorageLocationUseCase,
    GetAgentSettingsUseCase,
    GetClassifierLabelsUseCase,
    ListStorageDirectoryUseCase,
    ListStorageLocationsUseCase,
    ReplaceClassifierLabelsUseCase,
    TestAgentSettingsUseCase,
    TestStorageConnectionUseCase,
    UpdateAgentSettingsUseCase,
    UpdateStorageLocationUseCase,
)
from fileseek.shared.application.dependencies import resolve_dependency


def get_classifier_labels_use_case(
    request: Request,
) -> GetClassifierLabelsUseCase:
    return resolve_dependency(request, "get_classifier_labels_use_case")


def get_agent_settings_use_case(
    request: Request,
) -> GetAgentSettingsUseCase:
    return resolve_dependency(request, "get_agent_settings_use_case")


def get_update_agent_settings_use_case(
    request: Request,
) -> UpdateAgentSettingsUseCase:
    return resolve_dependency(request, "update_agent_settings_use_case")


def get_test_agent_settings_use_case(
    request: Request,
) -> TestAgentSettingsUseCase:
    return resolve_dependency(request, "test_agent_settings_use_case")


def get_replace_classifier_labels_use_case(
    request: Request,
) -> ReplaceClassifierLabelsUseCase:
    return resolve_dependency(request, "replace_classifier_labels_use_case")


def get_list_storage_locations_use_case(
    request: Request,
) -> ListStorageLocationsUseCase:
    return resolve_dependency(request, "list_storage_locations_use_case")


def get_list_storage_directory_use_case(
    request: Request,
) -> ListStorageDirectoryUseCase:
    return resolve_dependency(request, "list_storage_directory_use_case")


def get_create_storage_location_use_case(
    request: Request,
) -> CreateStorageLocationUseCase:
    return resolve_dependency(request, "create_storage_location_use_case")


def get_update_storage_location_use_case(
    request: Request,
) -> UpdateStorageLocationUseCase:
    return resolve_dependency(request, "update_storage_location_use_case")


def get_delete_storage_location_use_case(
    request: Request,
) -> DeleteStorageLocationUseCase:
    return resolve_dependency(request, "delete_storage_location_use_case")


def get_test_storage_connection_use_case(
    request: Request,
) -> TestStorageConnectionUseCase:
    return resolve_dependency(request, "test_storage_connection_use_case")
