from typing import Annotated

from fastapi import APIRouter, Depends, Query

from fileseek.features.settings.application.use_cases import (
    CreateStorageLocationUseCase,
    DeleteStorageLocationUseCase,
    GetClassifierLabelsUseCase,
    ListStorageDirectoryUseCase,
    ListStorageLocationsUseCase,
    ReplaceClassifierLabelsUseCase,
    TestStorageConnectionUseCase,
    UpdateStorageLocationUseCase,
)
from fileseek.features.settings.interfaces.http.dependencies import (
    get_classifier_labels_use_case,
    get_create_storage_location_use_case,
    get_delete_storage_location_use_case,
    get_list_storage_directory_use_case,
    get_list_storage_locations_use_case,
    get_replace_classifier_labels_use_case,
    get_test_storage_connection_use_case,
    get_update_storage_location_use_case,
)
from fileseek.features.settings.interfaces.http.mappers import (
    classifier_labels_request_to_command,
    classifier_labels_to_schema,
    connection_result_to_schema,
    delete_storage_location_command,
    get_classifier_labels_query,
    list_storage_locations_query,
    storage_create_request_to_command,
    storage_deletion_to_schema,
    storage_directory_query,
    storage_directory_to_schema,
    storage_location_to_schema,
    storage_update_request_to_command,
    test_storage_connection_command,
)
from fileseek.features.settings.interfaces.http.schemas import (
    ClassifierLabelsRequest,
    StorageLocationCreateRequest,
    StorageLocationUpdateRequest,
)
from fileseek.shared.domain.exceptions import ApplicationError
from fileseek.shared.envelope import error_response, success_response

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/classifier-labels")
async def get_classifier_labels(
    use_case: Annotated[
        GetClassifierLabelsUseCase,
        Depends(get_classifier_labels_use_case),
    ],
) -> dict[str, object]:
    try:
        labels = await use_case.execute(get_classifier_labels_query())
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(
        classifier_labels_to_schema(labels).model_dump(by_alias=True)
    )


@router.put("/classifier-labels")
async def replace_classifier_labels(
    body: ClassifierLabelsRequest,
    use_case: Annotated[
        ReplaceClassifierLabelsUseCase,
        Depends(get_replace_classifier_labels_use_case),
    ],
) -> dict[str, object]:
    try:
        labels = await use_case.execute(classifier_labels_request_to_command(body))
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(
        classifier_labels_to_schema(labels).model_dump(by_alias=True)
    )


@router.get("/storage-locations")
async def list_storage_locations(
    use_case: Annotated[
        ListStorageLocationsUseCase,
        Depends(get_list_storage_locations_use_case),
    ],
) -> dict[str, object]:
    try:
        locations = await use_case.execute(list_storage_locations_query())
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(
        [
            storage_location_to_schema(location).model_dump(by_alias=True)
            for location in locations
        ]
    )


@router.get("/storage-locations/{location_id}/directory")
async def list_storage_directory(
    use_case: Annotated[
        ListStorageDirectoryUseCase,
        Depends(get_list_storage_directory_use_case),
    ],
    location_id: str,
    path: str = Query(default=""),
) -> dict[str, object]:
    try:
        directory = await use_case.execute(
            storage_directory_query(location_id, path)
        )
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(
        storage_directory_to_schema(directory).model_dump(by_alias=True)
    )


@router.post("/storage-locations")
async def create_storage_location(
    body: StorageLocationCreateRequest,
    use_case: Annotated[
        CreateStorageLocationUseCase,
        Depends(get_create_storage_location_use_case),
    ],
) -> dict[str, object]:
    try:
        location = await use_case.execute(storage_create_request_to_command(body))
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(
        storage_location_to_schema(location).model_dump(by_alias=True)
    )


@router.put("/storage-locations/{location_id}")
async def update_storage_location(
    location_id: str,
    body: StorageLocationUpdateRequest,
    use_case: Annotated[
        UpdateStorageLocationUseCase,
        Depends(get_update_storage_location_use_case),
    ],
) -> dict[str, object]:
    try:
        location = await use_case.execute(
            storage_update_request_to_command(location_id, body)
        )
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(
        storage_location_to_schema(location).model_dump(by_alias=True)
    )


@router.delete("/storage-locations/{location_id}")
async def delete_storage_location(
    location_id: str,
    use_case: Annotated[
        DeleteStorageLocationUseCase,
        Depends(get_delete_storage_location_use_case),
    ],
) -> dict[str, object]:
    try:
        result = await use_case.execute(delete_storage_location_command(location_id))
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(
        storage_deletion_to_schema(result).model_dump(by_alias=True)
    )


@router.post("/storage-locations/{location_id}/test")
async def test_storage_connection(
    location_id: str,
    use_case: Annotated[
        TestStorageConnectionUseCase,
        Depends(get_test_storage_connection_use_case),
    ],
) -> dict[str, object]:
    try:
        result = await use_case.execute(test_storage_connection_command(location_id))
    except ApplicationError as exc:
        return error_response(str(exc))

    return success_response(
        connection_result_to_schema(result).model_dump(by_alias=True)
    )
