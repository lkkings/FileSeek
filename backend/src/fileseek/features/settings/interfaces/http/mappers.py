from fileseek.features.settings.application.commands import (
    CreateStorageLocationCommand,
    DeleteStorageLocationCommand,
    ReplaceClassifierLabelsCommand,
    TestAgentSettingsCommand,
    TestStorageConnectionCommand,
    UpdateAgentSettingsCommand,
    UpdateStorageLocationCommand,
)
from fileseek.features.settings.application.dto import (
    AgentSettingsDTO,
    ClassifierLabelsDTO,
    ConnectionTestResultDTO,
    StorageDirectoryDTO,
    StorageLocationDeletionDTO,
    StorageLocationDTO,
)
from fileseek.features.settings.application.queries import (
    GetClassifierLabelsQuery,
    ListStorageDirectoryQuery,
    ListStorageLocationsQuery,
)
from fileseek.features.settings.interfaces.http.schemas import (
    AgentSettingsRequest,
    AgentSettingsResponse,
    ClassifierLabelsRequest,
    ClassifierLabelsResponse,
    ConnectionTestResponse,
    StorageDirectoryEntryResponse,
    StorageDirectoryResponse,
    StorageLocationCreateRequest,
    StorageLocationDeletionResponse,
    StorageLocationResponse,
    StorageLocationUpdateRequest,
)


def agent_settings_to_schema(value: AgentSettingsDTO) -> AgentSettingsResponse:
    return AgentSettingsResponse(
        base_url=value.base_url,
        model=value.model,
        api_key_configured=value.api_key_configured,
    )


def agent_settings_request_to_command(
    body: AgentSettingsRequest,
) -> UpdateAgentSettingsCommand:
    return UpdateAgentSettingsCommand(
        base_url=body.base_url,
        model=body.model,
        api_key=body.api_key,
    )


def agent_settings_request_to_test_command(
    body: AgentSettingsRequest,
) -> TestAgentSettingsCommand:
    return TestAgentSettingsCommand(
        base_url=body.base_url,
        model=body.model,
        api_key=body.api_key,
    )


def classifier_labels_to_schema(value: ClassifierLabelsDTO) -> ClassifierLabelsResponse:
    return ClassifierLabelsResponse(
        document_labels=list(value.document_labels),
        image_labels=list(value.image_labels),
        video_labels=list(value.video_labels),
        version=value.version,
    )


def classifier_labels_request_to_command(
    body: ClassifierLabelsRequest,
) -> ReplaceClassifierLabelsCommand:
    return ReplaceClassifierLabelsCommand(
        document_labels=tuple(body.document_labels),
        image_labels=tuple(body.image_labels),
        video_labels=tuple(body.video_labels),
    )


def storage_location_to_schema(value: StorageLocationDTO) -> StorageLocationResponse:
    return StorageLocationResponse(
        id=value.id,
        type=value.type,
        name=value.name,
        protocol=value.protocol,
        endpoint=value.endpoint,
        root_path=value.root_path,
        account=value.account,
        status=value.status,
        is_system=value.is_system,
    )


def storage_create_request_to_command(
    body: StorageLocationCreateRequest,
) -> CreateStorageLocationCommand:
    return CreateStorageLocationCommand(
        id=body.id,
        name=body.name,
        protocol=body.protocol,
        endpoint=body.endpoint,
        root_path=body.root_path,
        account=body.account,
        password=body.password,
    )


def storage_update_request_to_command(
    location_id: str,
    body: StorageLocationUpdateRequest,
) -> UpdateStorageLocationCommand:
    return UpdateStorageLocationCommand(
        location_id=location_id,
        name=body.name,
        protocol=body.protocol,
        endpoint=body.endpoint,
        root_path=body.root_path,
        account=body.account,
        password=body.password,
    )


def storage_deletion_to_schema(
    value: StorageLocationDeletionDTO,
) -> StorageLocationDeletionResponse:
    return StorageLocationDeletionResponse(
        id=value.id,
        status=value.status,
        affected_files=value.affected_files,
    )


def connection_result_to_schema(
    value: ConnectionTestResultDTO,
) -> ConnectionTestResponse:
    return ConnectionTestResponse(success=value.success, message=value.message)


def get_classifier_labels_query() -> GetClassifierLabelsQuery:
    return GetClassifierLabelsQuery()


def list_storage_locations_query() -> ListStorageLocationsQuery:
    return ListStorageLocationsQuery()


def storage_directory_query(
    location_id: str,
    path: str,
) -> ListStorageDirectoryQuery:
    return ListStorageDirectoryQuery(storage_id=location_id, path=path)


def storage_directory_to_schema(
    value: StorageDirectoryDTO,
) -> StorageDirectoryResponse:
    return StorageDirectoryResponse(
        current_path=value.current_path,
        entries=[
            StorageDirectoryEntryResponse(
                name=entry.name,
                kind=entry.kind,
                source_path=entry.source_path,
                size=entry.size,
                modified=entry.modified.isoformat(),
            )
            for entry in value.entries
        ],
    )


def delete_storage_location_command(location_id: str) -> DeleteStorageLocationCommand:
    return DeleteStorageLocationCommand(location_id=location_id)


def test_storage_connection_command(location_id: str) -> TestStorageConnectionCommand:
    return TestStorageConnectionCommand(location_id=location_id)
