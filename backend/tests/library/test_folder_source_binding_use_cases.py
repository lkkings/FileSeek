from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fileseek.features.library.application.commands import (
    CreateFolderSourceBindingCommand,
    DeleteFolderSourceBindingCommand,
    UpdateFolderSourceBindingCommand,
)
from fileseek.features.library.application.ports import (
    FolderSourceRootPort,
    WatchableSourceRoot,
)
from fileseek.features.library.application.use_cases import (
    CreateFolderSourceBindingUseCase,
    DeleteFolderSourceBindingUseCase,
    ListFolderSourceBindingsUseCase,
    UpdateFolderSourceBindingUseCase,
)
from fileseek.features.library.domain.entities import Folder, FolderSourceBinding
from fileseek.features.settings.domain.entities import StorageLocation
from fileseek.features.settings.domain.repositories import StorageLocationRepository
from fileseek.features.settings.infrastructure.folder_source_root import (
    StorageFolderSourceRootResolver,
)
from fileseek.shared.domain.exceptions import ValidationError


class FakeFolderRepository:
    async def get_by_id(self, folder_id: str) -> Folder | None:
        if folder_id not in {"folder-1", "folder-2"}:
            return None
        return Folder(
            id=folder_id,
            name="Watched",
            icon_type="default",
            description="",
            modified=datetime.now(UTC),
        )


class FakeBindingRepository:
    def __init__(self, bindings: list[FolderSourceBinding] | None = None) -> None:
        self.bindings = bindings or []

    async def get_by_id(self, binding_id: str) -> FolderSourceBinding | None:
        return next((item for item in self.bindings if item.id == binding_id), None)

    async def list_by_folder(self, folder_id: str) -> list[FolderSourceBinding]:
        return [item for item in self.bindings if item.folder_id == folder_id]

    async def list_enabled(self) -> list[FolderSourceBinding]:
        return [item for item in self.bindings if item.enabled]

    async def list_all(self) -> list[FolderSourceBinding]:
        return list(self.bindings)

    async def save(self, binding: FolderSourceBinding) -> None:
        self.bindings = [item if item.id != binding.id else binding for item in self.bindings] + (
            [] if any(item.id == binding.id for item in self.bindings) else [binding]
        )

    async def delete(self, binding_id: str) -> None:
        self.bindings = [item for item in self.bindings if item.id != binding_id]


class FakeSeenRepository:
    def __init__(self, paths_by_binding: dict[str, set[str]] | None = None) -> None:
        self.paths_by_binding = paths_by_binding or {}

    async def list_paths(self, binding_id: str) -> set[str]:
        return self.paths_by_binding.get(binding_id, set())

    async def save(self, seen) -> None:
        self.paths_by_binding.setdefault(seen.binding_id, set()).add(seen.source_path)

    async def delete_path(self, binding_id: str, source_path: str) -> None:
        self.paths_by_binding.get(binding_id, set()).discard(source_path)

    async def replace_paths(
        self,
        binding_id: str,
        source_paths,
    ) -> None:
        self.paths_by_binding[binding_id] = set(source_paths)


class FakeRootResolver(FolderSourceRootPort):
    def __init__(self, paths: tuple[str, ...] = ()) -> None:
        self.paths = paths

    async def resolve(
        self,
        storage_id: str,
        source_path: str,
    ) -> WatchableSourceRoot:
        return WatchableSourceRoot(
            storage_id=storage_id,
            source_path=source_path,
            storage_root=Path("/storage"),
            filesystem_path=Path("/storage") / source_path,
        )

    async def list_file_paths(
        self,
        root: WatchableSourceRoot,
        *,
        recursive: bool,
    ) -> tuple[str, ...]:
        _ = recursive
        return self.paths


class FakeStorageRepository(StorageLocationRepository):
    def __init__(self, location: StorageLocation) -> None:
        self.location = location

    async def get_by_id(
        self,
        location_id: str,
        *,
        include_deleted: bool = False,
    ) -> StorageLocation | None:
        return self.location if include_deleted or self.location.is_active else None

    async def list_active_manageable(self) -> list[StorageLocation]:
        return [self.location] if self.location.is_active else []

    async def save(self, location: StorageLocation) -> StorageLocation:
        return location

    async def mark_deleted(self, location_id: str) -> bool:
        return False


@pytest.mark.asyncio
async def test_create_binding_leaves_history_for_initial_scan() -> None:
    binding_repo = FakeBindingRepository()
    seen_repo = FakeSeenRepository()
    use_case = CreateFolderSourceBindingUseCase(
        folder_repo=FakeFolderRepository(),
        binding_repo=binding_repo,
        root_resolver=FakeRootResolver(("old.pdf",)),
    )

    result = await use_case.execute(
        CreateFolderSourceBindingCommand(
            folder_id="folder-1",
            storage_id="nas",
            path="documents",
        )
    )

    assert result.enabled is True
    assert result.watch_status == "watching"
    assert seen_repo.paths_by_binding.get(result.id, set()) == set()


@pytest.mark.asyncio
async def test_overlapping_enabled_bindings_are_rejected() -> None:
    binding_repo = FakeBindingRepository(
        [
            FolderSourceBinding(
                id="existing",
                folder_id="folder-2",
                storage_id="local",
                source_path="/downloads",
            )
        ]
    )
    use_case = CreateFolderSourceBindingUseCase(
        folder_repo=FakeFolderRepository(),
        binding_repo=binding_repo,
        root_resolver=FakeRootResolver(),
    )

    with pytest.raises(ValidationError, match="重叠"):
        await use_case.execute(
            CreateFolderSourceBindingCommand(
                folder_id="folder-1",
                storage_id="local",
                path="/downloads/new",
            )
        )

    assert len(binding_repo.bindings) == 1


@pytest.mark.asyncio
async def test_update_clears_seen_state_when_source_changes() -> None:
    binding_repo = FakeBindingRepository(
        [
            FolderSourceBinding(
                id="binding-1",
                folder_id="folder-1",
                storage_id="local",
                source_path="/old",
            )
        ]
    )
    seen_repo = FakeSeenRepository({"binding-1": {"old.pdf"}})
    use_case = UpdateFolderSourceBindingUseCase(
        folder_repo=FakeFolderRepository(),
        binding_repo=binding_repo,
        seen_repo=seen_repo,
        root_resolver=FakeRootResolver(("new.pdf",)),
    )

    result = await use_case.execute(
        UpdateFolderSourceBindingCommand(
            binding_id="binding-1",
            folder_id="folder-1",
            storage_id="local",
            path="/new",
        )
    )

    assert result.source_path == "/new"
    assert seen_repo.paths_by_binding["binding-1"] == set()


@pytest.mark.asyncio
async def test_list_and_delete_bindings() -> None:
    binding_repo = FakeBindingRepository(
        [
            FolderSourceBinding(
                id="binding-1",
                folder_id="folder-1",
                storage_id="local",
                source_path="/downloads",
            )
        ]
    )
    list_result = await ListFolderSourceBindingsUseCase(binding_repo).execute("folder-1")
    await DeleteFolderSourceBindingUseCase(binding_repo).execute(
        DeleteFolderSourceBindingCommand("binding-1")
    )

    assert [item.id for item in list_result] == ["binding-1"]
    assert binding_repo.bindings == []


@pytest.mark.asyncio
async def test_storage_root_resolver_normalizes_local_and_mounted_paths(
    tmp_path: Path,
) -> None:
    local_root = tmp_path / "local"
    mounted_root = tmp_path / "nas"
    local_directory = local_root / "documents"
    mounted_directory = mounted_root / "documents"
    local_directory.mkdir(parents=True)
    mounted_directory.mkdir(parents=True)
    (local_directory / "report.pdf").write_text("local")
    (mounted_directory / "report.pdf").write_text("nas")

    local_resolver = StorageFolderSourceRootResolver(
        FakeStorageRepository(
            StorageLocation(
                id="local",
                type="local",
                name="Local",
                protocol="file",
                endpoint="file://localhost",
                root_path="/",
            )
        )
    )
    mounted_resolver = StorageFolderSourceRootResolver(
        FakeStorageRepository(
            StorageLocation(
                id="nas",
                type="nas",
                name="NAS",
                protocol="mounted",
                endpoint=str(mounted_root),
                root_path=str(mounted_root),
            )
        )
    )

    local_root_result = await local_resolver.resolve("local", str(local_directory))
    mounted_root_result = await mounted_resolver.resolve("nas", "documents")

    assert local_root_result.source_path == local_directory.as_posix()
    assert mounted_root_result.source_path == "documents"
    assert await local_resolver.list_file_paths(
        local_root_result,
        recursive=True,
    ) == ((local_directory / "report.pdf").as_posix(),)
    assert await mounted_resolver.list_file_paths(
        mounted_root_result,
        recursive=True,
    ) == ("documents/report.pdf",)


@pytest.mark.asyncio
async def test_storage_root_resolver_rejects_unsupported_sources() -> None:
    resolver = StorageFolderSourceRootResolver(
        FakeStorageRepository(
            StorageLocation(
                id="external",
                type="external",
                name="External",
                protocol="http",
                endpoint="https://example.com",
            )
        )
    )

    with pytest.raises(Exception, match="暂不支持监听"):
        await resolver.resolve("external", "/documents")
