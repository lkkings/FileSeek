from fileseek.features.settings.application.dto import (
    ClassifierLabelsDTO,
    StorageLocationDTO,
)
from fileseek.features.settings.domain.entities import (
    ClassifierLabelSet,
    StorageLocation,
)


def classifier_label_set_to_dto(value: ClassifierLabelSet) -> ClassifierLabelsDTO:
    return ClassifierLabelsDTO(
        document_labels=value.document_labels,
        image_labels=value.image_labels,
        video_labels=value.video_labels,
        version=value.version,
    )


def storage_location_to_dto(value: StorageLocation) -> StorageLocationDTO:
    return StorageLocationDTO(
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
