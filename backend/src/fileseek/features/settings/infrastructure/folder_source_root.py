from __future__ import annotations

from pathlib import Path

from fileseek.features.library.application.ports import (
    FolderSourceRootPort,
    WatchableSourceRoot,
)
from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.features.settings.domain.entities import StorageLocation
from fileseek.features.settings.domain.repositories import StorageLocationRepository


class StorageFolderSourceRootResolver(FolderSourceRootPort):
    def __init__(self, repository: StorageLocationRepository) -> None:
        self.repository = repository

    async def resolve(
        self,
        storage_id: str,
        source_path: str,
    ) -> WatchableSourceRoot:
        location = await self.repository.get_by_id(storage_id)
        if location is None:
            raise SourceUnavailableError(f"存储位置不存在: {storage_id}")
        if not location.is_active:
            raise SourceUnavailableError(f"存储位置不可用: {location.name}")
        if not _is_watchable(location):
            raise SourceUnavailableError(f"存储位置暂不支持监听: {location.name}")

        root = _storage_root(location).resolve(strict=False)
        requested = _requested_path(source_path)
        resolved = _resolve_requested(root, requested, location.type)
        try:
            resolved = resolved.resolve(strict=True)
        except OSError as exc:
            raise SourceUnavailableError("来源目录不可访问") from exc
        if not resolved.is_dir():
            raise SourceUnavailableError("来源路径不是目录")
        return WatchableSourceRoot(
            storage_id=storage_id,
            source_path=_source_path(location, root, resolved),
            storage_root=root,
            filesystem_path=resolved,
        )

    async def list_file_paths(
        self,
        root: WatchableSourceRoot,
        *,
        recursive: bool,
    ) -> tuple[str, ...]:
        candidates = (
            root.filesystem_path.rglob("*") if recursive else root.filesystem_path.iterdir()
        )
        return tuple(
            _relative_or_absolute_path(root, item) for item in candidates if item.is_file()
        )


def _relative_or_absolute_path(
    root: WatchableSourceRoot,
    item: Path,
) -> str:
    if root.source_path.startswith("/"):
        return item.as_posix()
    return item.relative_to(root.storage_root).as_posix()


def _is_watchable(location: StorageLocation) -> bool:
    if location.type == "local":
        return location.protocol == "file"
    if location.type == "nas":
        return location.protocol == "mounted"
    return False


def _storage_root(location: StorageLocation) -> Path:
    if location.type == "local":
        return Path(location.root_path or "/").expanduser()
    return Path(location.root_path or location.endpoint).expanduser()


def _requested_path(source_path: str) -> Path:
    value = source_path.strip()
    if not value:
        return Path()
    return Path(value).expanduser()


def _resolve_requested(
    root: Path,
    requested: Path,
    location_type: str,
) -> Path:
    if location_type == "local":
        if not requested.is_absolute():
            raise SourceUnavailableError("本地来源路径必须是绝对路径")
        return requested
    return requested if requested.is_absolute() else root / requested


def _source_path(
    location: StorageLocation,
    root: Path,
    resolved: Path,
) -> str:
    if location.type == "local":
        return resolved.as_posix()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise SourceUnavailableError("NAS 来源路径超出挂载根目录") from exc
