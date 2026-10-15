from __future__ import annotations

from datetime import UTC, datetime
from pathlib import PurePosixPath

from fileseek.features.library.application.commands import (
    CreateFolderSourceBindingCommand,
    DeleteFolderSourceBindingCommand,
    UpdateFolderSourceBindingCommand,
)
from fileseek.features.library.application.dto import FolderSourceBindingDTO
from fileseek.features.library.application.ports import FolderSourceRootPort
from fileseek.features.library.domain.entities import FolderSourceBinding
from fileseek.features.library.domain.repositories import (
    FolderRepository,
    FolderSourceBindingRepository,
    FolderSourceSeenRepository,
)
from fileseek.shared.domain.exceptions import NotFoundError, ValidationError
from fileseek.shared.domain.identifiers import generate_id


class ListFolderSourceBindingsUseCase:
    def __init__(
        self,
        binding_repo: FolderSourceBindingRepository,
    ) -> None:
        self.binding_repo = binding_repo

    async def execute(self, folder_id: str) -> list[FolderSourceBindingDTO]:
        return [_to_dto(binding) for binding in await self.binding_repo.list_by_folder(folder_id)]


class CreateFolderSourceBindingUseCase:
    def __init__(
        self,
        folder_repo: FolderRepository,
        binding_repo: FolderSourceBindingRepository,
        root_resolver: FolderSourceRootPort,
    ) -> None:
        self.folder_repo = folder_repo
        self.binding_repo = binding_repo
        self.root_resolver = root_resolver

    async def execute(
        self,
        command: CreateFolderSourceBindingCommand,
    ) -> FolderSourceBindingDTO:
        if await self.folder_repo.get_by_id(command.folder_id) is None:
            raise NotFoundError(f"文件夹不存在: {command.folder_id}")

        root = await self.root_resolver.resolve(command.storage_id, command.path)
        await _ensure_no_overlap(
            self.binding_repo,
            storage_id=root.storage_id,
            source_path=root.source_path,
            enabled=command.enabled,
        )
        duplicate = any(
            binding.storage_id == root.storage_id and binding.source_path == root.source_path
            for binding in await self.binding_repo.list_by_folder(command.folder_id)
        )
        if duplicate:
            raise ValidationError("该文件夹已绑定此来源目录")

        binding = FolderSourceBinding(
            id=generate_id("fsb"),
            folder_id=command.folder_id,
            storage_id=root.storage_id,
            source_path=root.source_path,
            recursive=command.recursive,
            enabled=command.enabled,
            watch_status="watching" if command.enabled else "disabled",
        )
        await self.binding_repo.save(binding)
        return _to_dto(binding)


class UpdateFolderSourceBindingUseCase:
    def __init__(
        self,
        folder_repo: FolderRepository,
        binding_repo: FolderSourceBindingRepository,
        seen_repo: FolderSourceSeenRepository,
        root_resolver: FolderSourceRootPort,
    ) -> None:
        self.folder_repo = folder_repo
        self.binding_repo = binding_repo
        self.seen_repo = seen_repo
        self.root_resolver = root_resolver

    async def execute(
        self,
        command: UpdateFolderSourceBindingCommand,
    ) -> FolderSourceBindingDTO:
        current = await self.binding_repo.get_by_id(command.binding_id)
        if current is None:
            raise NotFoundError(f"文件夹来源绑定不存在: {command.binding_id}")
        if await self.folder_repo.get_by_id(command.folder_id) is None:
            raise NotFoundError(f"文件夹不存在: {command.folder_id}")

        root = await self.root_resolver.resolve(command.storage_id, command.path)
        await _ensure_no_overlap(
            self.binding_repo,
            storage_id=root.storage_id,
            source_path=root.source_path,
            enabled=command.enabled,
            excluded_binding_id=current.id,
        )

        source_changed = (
            current.storage_id != root.storage_id
            or current.source_path != root.source_path
            or current.recursive != command.recursive
        )
        current.storage_id = root.storage_id
        current.source_path = root.source_path
        current.recursive = command.recursive
        current.enabled = command.enabled
        current.watch_status = "watching" if command.enabled else "disabled"
        current.updated_at = datetime.now(UTC)
        await self.binding_repo.save(current)
        if source_changed:
            await self.seen_repo.replace_paths(current.id, ())
        return _to_dto(current)


class DeleteFolderSourceBindingUseCase:
    def __init__(
        self,
        binding_repo: FolderSourceBindingRepository,
    ) -> None:
        self.binding_repo = binding_repo

    async def execute(self, command: DeleteFolderSourceBindingCommand) -> None:
        binding = await self.binding_repo.get_by_id(command.binding_id)
        if binding is None:
            raise NotFoundError(f"文件夹来源绑定不存在: {command.binding_id}")
        await self.binding_repo.delete(command.binding_id)


async def _ensure_no_overlap(
    binding_repo: FolderSourceBindingRepository,
    *,
    storage_id: str,
    source_path: str,
    enabled: bool,
    excluded_binding_id: str | None = None,
) -> None:
    if not enabled:
        return
    for binding in await binding_repo.list_enabled():
        if binding.id == excluded_binding_id:
            continue
        if binding.storage_id != storage_id:
            continue
        if _paths_overlap(binding.source_path, source_path):
            raise ValidationError("来源目录与其他启用中的绑定重叠")


def _paths_overlap(first: str, second: str) -> bool:
    first_path = PurePosixPath(first)
    second_path = PurePosixPath(second)
    return (
        first_path == second_path
        or first_path in second_path.parents
        or second_path in first_path.parents
    )


def _to_dto(binding: FolderSourceBinding) -> FolderSourceBindingDTO:
    last_error_at = binding.last_error_at.isoformat() if binding.last_error_at is not None else None
    return FolderSourceBindingDTO(
        id=binding.id,
        folder_id=binding.folder_id,
        storage_id=binding.storage_id,
        source_path=binding.source_path,
        recursive=binding.recursive,
        enabled=binding.enabled,
        watch_status=binding.watch_status,
        last_error=binding.last_error,
        last_error_at=last_error_at,
    )
