from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fileseek.shared.domain.file_types import FileType


COMPATIBILITY_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = COMPATIBILITY_DIRECTORY.parents[1]
FIXTURES_DIRECTORY = REPOSITORY_ROOT / "test"
CONTRACT_PATH = COMPATIBILITY_DIRECTORY / "file-types.json"
MANIFEST_PATH = FIXTURES_DIRECTORY / "manifest.json"


@dataclass(frozen=True)
class FileTypeSample:
    file_type: FileType
    file_name: str
    detected_file_type: FileType
    category: str
    media_type: str
    document_preview_support: str | None


@dataclass(frozen=True)
class FixtureManifestEntry:
    file_name: str
    file_type: str
    detected_file_type: str
    category: str
    media_type: str
    size: int
    sha256: str
    origin: str
    source: str
    source_url: str | None
    license: str


def load_file_type_samples() -> list[FileTypeSample]:
    with CONTRACT_PATH.open(encoding="utf-8") as contract_file:
        contract = json.load(contract_file)

    raw_types = cast(list[dict[str, object]], contract)
    return [
        FileTypeSample(
            file_type=FileType(raw_type["fileType"]),
            file_name=cast(str, raw_type["fileName"]),
            detected_file_type=FileType(raw_type["detectedFileType"]),
            category=cast(str, raw_type["category"]),
            media_type=cast(str, raw_type["mediaType"]),
            document_preview_support=cast(
                str | None,
                raw_type["documentPreviewSupport"],
            ),
        )
        for raw_type in raw_types
    ]


def fixture_path(sample: FileTypeSample) -> Path:
    return FIXTURES_DIRECTORY / sample.file_name


def load_fixture_manifest() -> list[FixtureManifestEntry]:
    with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    raw_entries = cast(list[dict[str, object]], manifest)
    return [
        FixtureManifestEntry(
            file_name=cast(str, raw_entry["fileName"]),
            file_type=cast(str, raw_entry["fileType"]),
            detected_file_type=cast(str, raw_entry["detectedFileType"]),
            category=cast(str, raw_entry["category"]),
            media_type=cast(str, raw_entry["mediaType"]),
            size=cast(int, raw_entry["size"]),
            sha256=cast(str, raw_entry["sha256"]),
            origin=cast(str, raw_entry["origin"]),
            source=cast(str, raw_entry["source"]),
            source_url=cast(str | None, raw_entry["sourceUrl"]),
            license=cast(str, raw_entry["license"]),
        )
        for raw_entry in raw_entries
    ]
