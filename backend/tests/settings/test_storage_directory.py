from __future__ import annotations

from pathlib import Path

import pytest

from fileseek.features.settings.application.dto import StorageDirectoryDTO
from fileseek.features.settings.application.queries import ListStorageDirectoryQuery
from fileseek.features.settings.application.use_cases import (
    ListStorageDirectoryUseCase,
)
from fileseek.features.settings.domain.entities import StorageLocation
from fileseek.features.settings.domain.exceptions import (
    StorageBrowseUnavailableError,
    StorageBrowseUnsupportedError,
)
from fileseek.features.settings.infrastructure import (
    FilesystemStorageDirectoryBrowser,
)
from fileseek.shared.domain.exceptions import NotFoundError


class FakeStorageLocationRepository:
    def __init__(self, locations: dict[str, StorageLocation]) -> None:
        self.locations = locations

    async def get_by_id(
        self,
        location_id: str,
        *,
        include_deleted: bool = False,
    ) -> StorageLocation | None:
        _ = include_deleted
        return self.locations.get(location_id)


class FakeStorageDirectoryBrowser:
    async def list_entries(
        self,
        location: StorageLocation,
        path: str,
    ) -> StorageDirectoryDTO:
        _ = location, path
        return StorageDirectoryDTO(current_path="", entries=())


def _location(
    location_id: str,
    *,
    type_: str = "nas",
    protocol: str = "mounted",
    status: str = "active",
) -> StorageLocation:
    return StorageLocation(
        id=location_id,
        type=type_,
        name=location_id,
        protocol=protocol,
        endpoint="/storage",
        root_path="/storage",
        status=status,
    )


@pytest.mark.asyncio
async def test_storage_directory_use_case_allows_local_and_mounted() -> None:
    repository = FakeStorageLocationRepository(
        {
            "local": _location("local", type_="local", protocol="file"),
            "nas1": _location("nas1"),
        }
    )
    browser = FakeStorageDirectoryBrowser()
    use_case = ListStorageDirectoryUseCase(repository, browser)

    await use_case.execute(ListStorageDirectoryQuery(storage_id="local"))
    await use_case.execute(
        ListStorageDirectoryQuery(storage_id="nas1", path="documents")
    )


@pytest.mark.asyncio
async def test_storage_directory_use_case_rejects_deleted_and_unsupported() -> None:
    repository = FakeStorageLocationRepository(
        {
            "deleted": _location("deleted", status="deleted"),
            "webdav": _location("webdav", protocol="webdav"),
            "external": _location("external", type_="external", protocol="http"),
        }
    )
    use_case = ListStorageDirectoryUseCase(repository, FakeStorageDirectoryBrowser())

    with pytest.raises(StorageBrowseUnavailableError):
        await use_case.execute(ListStorageDirectoryQuery(storage_id="deleted"))
    with pytest.raises(StorageBrowseUnsupportedError):
        await use_case.execute(ListStorageDirectoryQuery(storage_id="webdav"))
    with pytest.raises(StorageBrowseUnsupportedError):
        await use_case.execute(ListStorageDirectoryQuery(storage_id="external"))


@pytest.mark.asyncio
async def test_storage_directory_use_case_rejects_missing_location() -> None:
    use_case = ListStorageDirectoryUseCase(
        FakeStorageLocationRepository({}),
        FakeStorageDirectoryBrowser(),
    )

    with pytest.raises(NotFoundError):
        await use_case.execute(ListStorageDirectoryQuery(storage_id="missing"))


@pytest.mark.asyncio
async def test_storage_directory_browser_lists_sorted_entries(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    documents = root / "Documents"
    reports = root / "Reports"
    image = root / "image.png"
    markdown = root / "notes.md"
    jpeg = root / "photo.jpeg"
    archive = root / "archive.zip"
    audio = root / "song.mp3"
    document = documents / "report.pdf"
    documents.mkdir(parents=True)
    reports.mkdir()
    image.write_bytes(b"image")
    markdown.write_bytes(b"notes")
    jpeg.write_bytes(b"photo")
    archive.write_bytes(b"archive")
    audio.write_bytes(b"audio")
    document.write_bytes(b"document")
    browser = FilesystemStorageDirectoryBrowser()

    directory = await browser.list_entries(
        StorageLocation(
            id="nas1",
            type="nas",
            name="NAS 1",
            protocol="mounted",
            endpoint=str(root),
            root_path=str(root),
        ),
        "",
    )
    local_directory = await browser.list_entries(
        StorageLocation(
            id="local",
            type="local",
            name="Local",
            protocol="file",
            endpoint=str(root),
            root_path=str(root),
        ),
        str(root),
    )

    entries = directory.entries
    assert directory.current_path == ""
    assert [entry.name for entry in entries] == [
        "Documents",
        "Reports",
        "image.png",
        "notes.md",
        "photo.jpeg",
    ]
    assert [entry.kind for entry in entries[:2]] == ["directory", "directory"]
    assert entries[2].source_path == "image.png"
    assert entries[2].size == len(b"image")
    assert local_directory.entries[2].source_path == str(image)
    assert local_directory.current_path == str(root)


@pytest.mark.asyncio
async def test_local_system_directory_defaults_to_downloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    downloads = home / "Downloads"
    downloads.mkdir()
    (downloads / "document.pdf").write_bytes(b"document")
    monkeypatch.setattr(Path, "home", lambda: home)
    browser = FilesystemStorageDirectoryBrowser()
    location = StorageLocation(
        id="local",
        type="local",
        name="Local",
        protocol="file",
        endpoint="file://localhost/",
        root_path="/",
        is_system=True,
    )

    directory = await browser.list_entries(location, "")

    assert directory.current_path == str(downloads)
    assert [entry.source_path for entry in directory.entries] == [
        str(downloads / "document.pdf")
    ]


@pytest.mark.asyncio
async def test_local_storage_can_browse_outside_its_configured_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "library-root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "report.pdf").write_bytes(b"report")
    browser = FilesystemStorageDirectoryBrowser()
    location = StorageLocation(
        id="local",
        type="local",
        name="Local",
        protocol="file",
        endpoint="file://localhost",
        root_path=str(root),
        is_system=True,
    )

    directory = await browser.list_entries(location, str(outside))

    assert directory.current_path == str(outside)
    assert [entry.source_path for entry in directory.entries] == [
        str(outside / "report.pdf")
    ]


@pytest.mark.asyncio
async def test_mounted_directory_accepts_pasted_absolute_path(tmp_path: Path) -> None:
    root = tmp_path / "nas"
    documents = root / "Documents"
    documents.mkdir(parents=True)
    browser = FilesystemStorageDirectoryBrowser()
    location = StorageLocation(
        id="nas1",
        type="nas",
        name="NAS 1",
        protocol="mounted",
        endpoint=str(root),
        root_path=str(root),
    )

    directory = await browser.list_entries(location, str(documents))

    assert directory.current_path == "Documents"
    assert directory.entries == ()


@pytest.mark.asyncio
async def test_storage_directory_browser_rejects_unsafe_paths(tmp_path: Path) -> None:
    browser = FilesystemStorageDirectoryBrowser()

    with pytest.raises(StorageBrowseUnavailableError):
        await browser.list_entries(_location("nas1"), "../escape")
    with pytest.raises(StorageBrowseUnavailableError):
        await browser.list_entries(_location("nas1"), "missing")


@pytest.mark.asyncio
async def test_storage_directory_browser_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    (root / "escape.txt").symlink_to(outside)
    browser = FilesystemStorageDirectoryBrowser()

    with pytest.raises(StorageBrowseUnavailableError):
        await browser.list_entries(_location("nas1"), "")
