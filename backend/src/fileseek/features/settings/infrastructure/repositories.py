from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from uuid import uuid4

from tortoise.transactions import in_transaction

from fileseek.features.settings.domain.entities import (
    ClassifierLabelSet,
    StorageLocation,
    StorageLocationType,
    StorageProtocol,
    StorageStatus,
)
from fileseek.infrastructure.database.models import (
    ClassifierLabelModel,
    StorageLocationModel,
)


def _to_storage_location(model: StorageLocationModel) -> StorageLocation:
    return StorageLocation(
        id=model.id,
        type=cast(StorageLocationType, model.type),
        name=model.name,
        protocol=cast(StorageProtocol, model.protocol),
        endpoint=model.endpoint,
        root_path=model.root_path,
        account=model.account,
        password=model.password,
        status=cast(StorageStatus, model.status),
        is_system=model.is_system,
    )


class TortoiseStorageLocationRepository:
    async def get_by_id(
        self,
        location_id: str,
        *,
        include_deleted: bool = False,
    ) -> StorageLocation | None:
        query = StorageLocationModel.filter(id=location_id)
        if not include_deleted:
            query = query.filter(status="active")
        model = await query.first()
        return _to_storage_location(model) if model else None

    async def list_active_manageable(self) -> list[StorageLocation]:
        models = (
            await StorageLocationModel.filter(
                status="active",
                type__in=["local", "nas"],
            )
            .order_by("type", "name")
        )
        return [_to_storage_location(model) for model in models]

    async def save(self, location: StorageLocation) -> StorageLocation:
        model, _ = await StorageLocationModel.update_or_create(
            id=location.id,
            defaults={
                "type": location.type,
                "name": location.name,
                "protocol": location.protocol,
                "endpoint": location.endpoint,
                "root_path": location.root_path,
                "account": location.account,
                "password": location.password,
                "status": location.status,
                "is_system": location.is_system,
            },
        )
        return _to_storage_location(model)

    async def mark_deleted(self, location_id: str) -> bool:
        updated = await StorageLocationModel.filter(
            id=location_id,
            is_system=False,
            status="active",
        ).update(status="deleted")
        return updated > 0


class TortoiseClassifierLabelRepository:
    async def get_label_set(self) -> ClassifierLabelSet:
        models = await ClassifierLabelModel.filter(enabled=True).order_by(
            "category",
            "label",
        )
        labels: dict[str, list[str]] = {
            "document": [],
            "image": [],
            "video": [],
        }
        for model in models:
            if model.category in labels:
                labels[model.category].append(model.label)

        return ClassifierLabelSet(
            document_labels=tuple(labels["document"]),
            image_labels=tuple(labels["image"]),
            video_labels=tuple(labels["video"]),
        )

    async def replace(self, labels: Sequence[str], category: str) -> None:
        async with in_transaction():
            await ClassifierLabelModel.filter(category=category).delete()
            await ClassifierLabelModel.bulk_create(
                [
                    ClassifierLabelModel(
                        id=uuid4().hex,
                        category=category,
                        label=label,
                    )
                    for label in labels
                ]
            )

    async def replace_label_set(self, labels: ClassifierLabelSet) -> None:
        async with in_transaction():
            await ClassifierLabelModel.all().delete()
            await ClassifierLabelModel.bulk_create(
                [
                    ClassifierLabelModel(
                        id=uuid4().hex,
                        category=category,
                        label=label,
                    )
                    for category, category_labels in (
                        ("document", labels.document_labels),
                        ("image", labels.image_labels),
                        ("video", labels.video_labels),
                    )
                    for label in category_labels
                ]
            )
