from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256

from tortoise.transactions import in_transaction

from fileseek.features.library.domain.entities import (
    FolderSourceBinding,
    FolderSourceSeen,
)
from fileseek.infrastructure.database.models import (
    FolderSourceBindingModel,
    FolderSourceSeenModel,
)


def _to_binding(model: FolderSourceBindingModel) -> FolderSourceBinding:
    return FolderSourceBinding(
        id=model.id,
        folder_id=model.folder_id,
        storage_id=model.storage_id,
        source_path=model.source_path,
        recursive=model.recursive,
        enabled=model.enabled,
        watch_status=model.watch_status,
        last_error=model.last_error,
        last_error_at=model.last_error_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class FolderSourceBindingRepositoryImpl:
    async def get_by_id(self, binding_id: str) -> FolderSourceBinding | None:
        model = await FolderSourceBindingModel.get_or_none(id=binding_id)
        return _to_binding(model) if model else None

    async def list_by_folder(self, folder_id: str) -> list[FolderSourceBinding]:
        models = await FolderSourceBindingModel.filter(folder_id=folder_id).order_by(
            "created_at",
            "id",
        )
        return [_to_binding(model) for model in models]

    async def list_enabled(self) -> list[FolderSourceBinding]:
        models = await FolderSourceBindingModel.filter(enabled=True).order_by(
            "created_at",
            "id",
        )
        return [_to_binding(model) for model in models]

    async def list_all(self) -> list[FolderSourceBinding]:
        models = await FolderSourceBindingModel.all().order_by(
            "created_at",
            "id",
        )
        return [_to_binding(model) for model in models]

    async def save(self, binding: FolderSourceBinding) -> None:
        await FolderSourceBindingModel.update_or_create(
            id=binding.id,
            defaults={
                "folder_id": binding.folder_id,
                "storage_id": binding.storage_id,
                "source_path": binding.source_path,
                "recursive": binding.recursive,
                "enabled": binding.enabled,
                "watch_status": binding.watch_status,
                "last_error": binding.last_error,
                "last_error_at": binding.last_error_at,
            },
        )

    async def delete(self, binding_id: str) -> None:
        await FolderSourceBindingModel.filter(id=binding_id).delete()


class FolderSourceSeenRepositoryImpl:
    async def list_paths(self, binding_id: str) -> set[str]:
        rows = await FolderSourceSeenModel.filter(binding_id=binding_id).values_list(
            "source_path",
            flat=True,
        )
        return set(rows)

    async def save(self, seen: FolderSourceSeen) -> None:
        model = await FolderSourceSeenModel.get_or_none(
            binding_id=seen.binding_id,
            source_path=seen.source_path,
        )
        if model is None:
            await FolderSourceSeenModel.create(
                id=seen.id,
                binding_id=seen.binding_id,
                source_path=seen.source_path,
                outcome=seen.outcome,
            )
            return
        model.outcome = seen.outcome
        await model.save(update_fields=["outcome"])

    async def delete_path(self, binding_id: str, source_path: str) -> None:
        await FolderSourceSeenModel.filter(
            binding_id=binding_id,
            source_path=source_path,
        ).delete()

    async def replace_paths(
        self,
        binding_id: str,
        source_paths: Iterable[str],
    ) -> None:
        values = sorted(set(source_paths))
        async with in_transaction():
            await FolderSourceSeenModel.filter(binding_id=binding_id).delete()
            await FolderSourceSeenModel.bulk_create(
                [
                    FolderSourceSeenModel(
                        id=_seen_id(binding_id, source_path),
                        binding_id=binding_id,
                        source_path=source_path,
                        outcome="seen",
                    )
                    for source_path in values
                ]
            )


def _seen_id(binding_id: str, source_path: str) -> str:
    digest = sha256(f"{binding_id}:{source_path}".encode()).hexdigest()
    return f"s_{digest}"


__all__ = [
    "FolderSourceBindingRepositoryImpl",
    "FolderSourceSeenRepositoryImpl",
]
