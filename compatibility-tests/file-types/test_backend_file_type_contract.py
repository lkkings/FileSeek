from __future__ import annotations

import csv
import hashlib
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

import av
import pytest
from docx import Document
from PIL import Image
from pypdf import PdfReader

from fileseek.config.settings import Settings
from fileseek.features.library.application.commands import AddFileCommand
from fileseek.features.library.application.ports import SourceMetadata
from fileseek.features.library.application.use_cases.add_file import AddFileUseCase
from fileseek.features.library.domain.entities import File
from fileseek.features.settings.infrastructure.source_access import LocalSourceFile
from fileseek.features.tasks.domain.entities import Task
from fileseek.features.tasks.domain.ports import ClassifierLabelSnapshot
from fileseek.shared.domain.file_types import FileCategory, FileType
from fileseek.shared.utils.file_utils import detect_file_type_from_file

from file_type_contract import (
    FIXTURES_DIRECTORY,
    fixture_path,
    load_file_type_samples,
    load_fixture_manifest,
)


class FakeFileSource:
    async def resolve(self, storage_id: str, source_path: str) -> LocalSourceFile:
        _ = storage_id
        return LocalSourceFile(Path(source_path))

    async def read_metadata(
        self,
        storage_id: str,
        source_path: str,
    ) -> SourceMetadata:
        stat = (await self.resolve(storage_id, source_path)).stat()
        return SourceMetadata(
            size=int(stat["size"]),
            modified=datetime.fromtimestamp(float(stat["mtime"]), tz=UTC),
        )


class FakeFileRepository:
    def __init__(self) -> None:
        self.files: dict[str, File] = {}

    async def get_by_id(self, file_id: str) -> File | None:
        return self.files.get(file_id)

    async def save(self, file: File) -> None:
        self.files[file.id] = file


class FakeFolderRepository:
    async def get_by_id(self, folder_id: str):
        _ = folder_id


class FakeTaskManager:
    def __init__(self) -> None:
        self.tasks: list[Task] = []

    async def create(self, task: Task) -> Task:
        self.tasks.append(task)
        return task


class FakeLabelProvider:
    async def get_snapshot(self) -> ClassifierLabelSnapshot:
        return ClassifierLabelSnapshot(
            document_labels=("合同",),
            image_labels=("照片",),
            video_labels=("课程",),
            version="version-1",
        )


def test_file_type_contract_covers_every_backend_file_type() -> None:
    samples = load_file_type_samples()
    contract_types = {sample.file_type for sample in samples}
    backend_types = set(FileType)

    assert contract_types == backend_types
    assert len({sample.file_name for sample in samples}) == len(samples)


def test_fixture_manifest_matches_every_real_sample() -> None:
    samples = {sample.file_name: sample for sample in load_file_type_samples()}
    manifest = {entry.file_name: entry for entry in load_fixture_manifest()}

    assert set(manifest) == set(samples)
    assert {
        path.name
        for path in FIXTURES_DIRECTORY.iterdir()
        if path.is_file()
    } == set(samples) | {"manifest.json", "README.md"}

    for file_name, entry in manifest.items():
        sample = samples[file_name]
        content = (FIXTURES_DIRECTORY / file_name).read_bytes()

        assert entry.file_type == sample.file_type.value
        assert entry.detected_file_type == sample.detected_file_type.value
        assert entry.category == sample.category
        assert entry.media_type == sample.media_type
        assert entry.size == len(content)
        assert entry.sha256 == hashlib.sha256(content).hexdigest()
        assert entry.origin in {"downloaded", "generated", "derived"}
        assert entry.source
        assert entry.license


@pytest.mark.parametrize(
    "sample",
    load_file_type_samples(),
    ids=lambda sample: sample.file_type.value,
)
def test_backend_detects_real_fixture_file_type(sample) -> None:
    detected = detect_file_type_from_file(fixture_path(sample))

    assert detected is sample.detected_file_type
    assert detected is not None
    assert detected.category is FileCategory(sample.category)
    assert detected.media_type == sample.media_type


@pytest.mark.parametrize(
    "sample",
    load_file_type_samples(),
    ids=lambda sample: sample.file_type.value,
)
def test_real_fixture_can_be_parsed(sample) -> None:
    path = fixture_path(sample)

    match sample.file_type:
        case FileType.PDF:
            assert len(PdfReader(path).pages) == 1
        case FileType.DOCX:
            assert Document(str(path)).paragraphs[0].text
        case FileType.XLSX | FileType.PPTX:
            _validate_ooxml(path)
        case FileType.ODT | FileType.ODS | FileType.ODP:
            _validate_odf(path)
        case FileType.DOC | FileType.XLS | FileType.PPT:
            assert path.read_bytes()[:8] == bytes.fromhex("D0CF11E0A1B11AE1")
        case FileType.RTF:
            content = path.read_text(encoding="utf-8")
            assert content.startswith(r"{\rtf1") and content.endswith("}")
        case FileType.TXT | FileType.MARKDOWN:
            assert path.read_text(encoding="utf-8")
        case FileType.HTML:
            assert b"<html" in path.read_bytes().lower()
        case FileType.XML | FileType.SVG:
            ElementTree.parse(path)
        case FileType.CSV:
            assert len(list(csv.reader(path.open(encoding="utf-8")))) == 2
        case (
            FileType.JPG
            | FileType.PNG
            | FileType.GIF
            | FileType.BMP
            | FileType.WEBP
            | FileType.TIFF
            | FileType.ICO
        ):
            with Image.open(path) as image:
                image.verify()
        case FileType.HEIC | FileType.HEIF:
            with av.open(path) as container:
                assert container.streams
        case _:
            _decode_video(path)


@pytest.mark.asyncio
async def test_add_file_accepts_every_real_fixture_file_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        lib_root=tmp_path / "library",
        db_path=tmp_path / "library/app.db",
        vector_db_path=tmp_path / "library/vectors",
        embedding_model_cache_dir=tmp_path / "library/models",
        recycle_dir=tmp_path / "library/recycle",
        temp_dir=tmp_path / "library/temp",
    )
    monkeypatch.setattr(
        "fileseek.features.library.application.use_cases.add_file.get_settings",
        lambda: settings,
    )
    file_repository = FakeFileRepository()
    task_manager = FakeTaskManager()
    use_case = AddFileUseCase(
        file_repository,
        FakeFolderRepository(),
        task_manager,
        FakeFileSource(),
        FakeLabelProvider(),
    )
    samples = load_file_type_samples()

    for sample in samples:
        result = await use_case.execute(
            AddFileCommand(
                folder_id="",
                path=str(fixture_path(sample)),
                storage_id="local",
            )
        )

        file = file_repository.files[result.file_id]
        assert file.file_type is sample.detected_file_type
        assert file.category.value == sample.category
        assert file.file_type.media_type == sample.media_type
        temp_path = Path(task_manager.tasks[-1].metadata["temp_path"])
        assert temp_path.suffix == Path(sample.file_name).suffix

    assert len(file_repository.files) == len(samples)
    assert len(task_manager.tasks) == len(samples)


def _validate_ooxml(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        assert "[Content_Types].xml" in archive.namelist()
        ElementTree.fromstring(archive.read("[Content_Types].xml"))


def _validate_odf(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        mimetype = archive.read("mimetype")
        ElementTree.fromstring(archive.read("content.xml"))
    assert mimetype.startswith(b"application/vnd.oasis.opendocument.")


def _decode_video(path: Path) -> None:
    with av.open(path) as container:
        stream = container.streams.video[0]
        decoded_frames = sum(
            1 for _ in container.decode(stream)
        )
        assert decoded_frames > 0
