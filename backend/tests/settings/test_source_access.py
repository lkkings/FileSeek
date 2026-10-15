from __future__ import annotations

from pathlib import Path

import pytest

from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.features.settings.domain.entities import StorageLocation
from fileseek.features.settings.infrastructure import (
    NasSourceFile,
    StorageSourceResolver,
    TortoiseStorageLocationRepository,
)


@pytest.mark.asyncio
async def test_resolver_reads_local_absolute_path(
    settings,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"local")
    repository = TortoiseStorageLocationRepository()
    resolver = StorageSourceResolver(repository)

    resolved = await resolver.resolve("local", str(source))

    with resolved.open("rb") as file:
        assert file.read() == b"local"


@pytest.mark.asyncio
async def test_resolver_reads_local_file_uri(
    settings,
    tmp_path: Path,
) -> None:
    source = tmp_path / "中文 文件.txt"
    source.write_bytes(b"local uri")
    repository = TortoiseStorageLocationRepository()
    resolver = StorageSourceResolver(repository)

    resolved = await resolver.resolve("local", source.as_uri())

    with resolved.open("rb") as file:
        assert file.read() == b"local uri"


@pytest.mark.asyncio
async def test_resolver_reads_local_relative_path_from_storage_root(
    settings,
    tmp_path: Path,
) -> None:
    source = tmp_path / "nested" / "source.txt"
    source.parent.mkdir()
    source.write_bytes(b"local relative")
    repository = TortoiseStorageLocationRepository()
    await repository.save(
        StorageLocation(
            id="local",
            type="local",
            name="本地存储",
            protocol="file",
            endpoint="file://localhost",
            root_path=str(tmp_path),
        )
    )
    resolver = StorageSourceResolver(repository)

    resolved = await resolver.resolve("local", "nested/source.txt")
    metadata = await resolver.read_metadata("local", "nested/source.txt")

    with resolved.open("rb") as file:
        assert file.read() == b"local relative"
    assert metadata.size == len(b"local relative")


@pytest.mark.asyncio
async def test_resolver_reads_external_uri(settings, tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"external")
    repository = TortoiseStorageLocationRepository()
    resolver = StorageSourceResolver(repository)

    resolved = await resolver.resolve("external", source.as_uri())

    with resolved.open("rb") as file:
        assert file.read() == b"external"


@pytest.mark.asyncio
async def test_resolver_reads_mounted_nas_relative_path(
    settings,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"nas")
    repository = TortoiseStorageLocationRepository()
    await repository.save(
        StorageLocation(
            id="nas1",
            type="nas",
            name="NAS 1",
            protocol="mounted",
            endpoint=str(tmp_path),
            root_path=str(tmp_path),
        )
    )
    resolver = StorageSourceResolver(repository)

    resolved = await resolver.resolve("nas1", "source.txt")
    metadata = await resolver.read_metadata("nas1", "source.txt")

    assert isinstance(resolved, NasSourceFile)
    assert resolved.relative_path == Path("source.txt")
    with resolved.open("rb") as file:
        assert file.read() == b"nas"
    assert metadata.size == 3


@pytest.mark.asyncio
async def test_resolver_reads_mounted_nas_absolute_path_inside_root(
    settings,
    tmp_path: Path,
) -> None:
    source = tmp_path / "nested" / "source.txt"
    source.parent.mkdir()
    source.write_bytes(b"absolute")
    repository = TortoiseStorageLocationRepository()
    await repository.save(
        StorageLocation(
            id="nas1",
            type="nas",
            name="NAS 1",
            protocol="mounted",
            endpoint=str(tmp_path),
            root_path=str(tmp_path),
        )
    )
    resolver = StorageSourceResolver(repository)

    resolved = await resolver.resolve("nas1", str(source))

    with resolved.open("rb") as file:
        assert file.read() == b"absolute"


@pytest.mark.asyncio
async def test_resolver_rejects_mounted_nas_path_outside_root(
    settings,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    repository = TortoiseStorageLocationRepository()
    await repository.save(
        StorageLocation(
            id="nas1",
            type="nas",
            name="NAS 1",
            protocol="mounted",
            endpoint=str(tmp_path / "nas"),
            root_path=str(tmp_path / "nas"),
        )
    )
    resolver = StorageSourceResolver(repository)

    with pytest.raises(SourceUnavailableError, match="超出挂载根目录"):
        await resolver.resolve("nas1", str(outside))


@pytest.mark.asyncio
async def test_resolver_rejects_mounted_nas_symlink_escape(
    settings,
    tmp_path: Path,
) -> None:
    root = tmp_path / "nas"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    symlink = root / "escape.txt"
    symlink.symlink_to(outside)
    repository = TortoiseStorageLocationRepository()
    await repository.save(
        StorageLocation(
            id="nas1",
            type="nas",
            name="NAS 1",
            protocol="mounted",
            endpoint=str(root),
            root_path=str(root),
        )
    )
    resolver = StorageSourceResolver(repository)

    with pytest.raises(SourceUnavailableError, match="超出挂载根目录"):
        await resolver.resolve("nas1", "escape.txt")


@pytest.mark.asyncio
async def test_resolver_rejects_missing_and_unsafe_sources(settings) -> None:
    repository = TortoiseStorageLocationRepository()
    resolver = StorageSourceResolver(repository)

    with pytest.raises(SourceUnavailableError):
        await resolver.read_metadata("local", "/definitely/missing/file.txt")
    with pytest.raises(SourceUnavailableError):
        await resolver.resolve("external", "../escape.txt")
