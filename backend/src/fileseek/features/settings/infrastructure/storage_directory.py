from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fileseek.features.settings.application.dto import StorageDirectoryDTO, StorageDirectoryEntryDTO
from fileseek.features.settings.domain.entities import StorageLocation
from fileseek.features.settings.domain.exceptions import StorageBrowseUnavailableError
from fileseek.shared.domain.file_types import FileType

SUPPORTED_FILE_SUFFIXES = {file_type.value for file_type in FileType if file_type.is_support} | {
    "htm",
    "jpeg",
    "md",
    "tif",
}


class FilesystemStorageDirectoryBrowser:
    async def list_entries(
        self,
        location: StorageLocation,
        path: str,
    ) -> StorageDirectoryDTO:
        requested = self._requested_path(location, path)
        root = self._root(location, requested)
        if ".." in Path(path).parts or ".." in requested.parts:
            raise StorageBrowseUnavailableError("目录路径不能包含上级目录")

        candidate = requested if requested.is_absolute() else root / requested
        try:
            resolved_root = root.resolve(strict=True)
            resolved = candidate.resolve(strict=True)
            if location.type != "local" and not resolved.is_relative_to(resolved_root):
                raise StorageBrowseUnavailableError("目录不可访问或超出存储根目录")
            if not resolved.is_dir():
                raise StorageBrowseUnavailableError("目录不可访问或超出存储根目录")

            entries: list[StorageDirectoryEntryDTO] = []
            for item in resolved.iterdir():
                resolved_item = item.resolve(strict=True)
                if location.type != "local" and not resolved_item.is_relative_to(resolved_root):
                    raise StorageBrowseUnavailableError("目录包含超出存储根目录的链接")
                metadata = resolved_item.stat()
                if not resolved_item.is_dir():
                    suffix = resolved_item.suffix.lower().removeprefix(".")
                    if suffix not in SUPPORTED_FILE_SUFFIXES:
                        continue
                entries.append(
                    StorageDirectoryEntryDTO(
                        name=resolved_item.name,
                        kind="directory" if resolved_item.is_dir() else "file",
                        source_path=self._source_path(location, resolved_root, resolved_item),
                        size=0 if resolved_item.is_dir() else metadata.st_size,
                        modified=datetime.fromtimestamp(metadata.st_mtime),
                    )
                )
        except OSError as exc:
            raise StorageBrowseUnavailableError("目录不可访问") from exc

        return StorageDirectoryDTO(
            current_path=self._current_path(location, resolved_root, resolved),
            entries=tuple(
                sorted(
                    entries,
                    key=lambda entry: (entry.kind != "directory", entry.name.casefold()),
                )
            ),
        )

    @staticmethod
    def _root(location: StorageLocation, requested: Path) -> Path:
        if location.type == "local":
            anchor = requested.anchor if requested.is_absolute() else Path.cwd().anchor
            return Path(anchor)
        root_value = location.root_path or location.endpoint
        return Path(root_value)

    def _requested_path(self, location: StorageLocation, path: str) -> Path:
        requested = Path(path.strip()).expanduser()
        if path.strip():
            return requested
        if location.type == "local":
            return Path.home() / "Downloads"
        return Path()

    @staticmethod
    def _current_path(
        location: StorageLocation,
        root: Path,
        current: Path,
    ) -> str:
        if location.type == "local":
            return str(current)
        relative = current.relative_to(root).as_posix()
        return "" if relative == "." else relative

    @staticmethod
    def _source_path(
        location: StorageLocation,
        root: Path,
        item: Path,
    ) -> str:
        if location.type == "local":
            return str(item)
        return item.relative_to(root).as_posix()
