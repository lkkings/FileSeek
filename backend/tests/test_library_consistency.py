import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from fileseek.db import FileRecord, FileRepository, connect, migrate
from fileseek.library.consistency import (
    ConsistencyReport,
    Finding,
    apply_report,
    check_files,
    scan_library,
)
from fileseek.library.hashing import hash_bytes

PAYLOAD = b"the original bytes"
DIGEST = hash_bytes(PAYLOAD)


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def files(db: sqlite3.Connection) -> FileRepository:
    return FileRepository(db)


@pytest.fixture
def library(tmp_path: Path) -> Path:
    root = tmp_path / "library" / "images"
    root.mkdir(parents=True)
    return root


def add_file(
    files: FileRepository,
    library: Path,
    file_id: str = "f1",
    *,
    payload: bytes | None = PAYLOAD,
    content_hash: str = DIGEST,
    index_state: str = "indexed",
) -> FileRecord:
    target = library / f"{file_id}.jpg"
    if payload is not None:
        target.write_bytes(payload)
    record = FileRecord(
        id=file_id,
        path=str(target),
        filename=target.name,
        media_type="image",
        size=len(payload) if payload else 0,
        content_hash=content_hash,
        added_at=1_700_000_000,
        index_state=index_state,  # type: ignore[arg-type]
    )
    files.add(record)
    return record


def test_intact_file_is_reported_clean(files: FileRepository, library: Path) -> None:
    record = add_file(files, library)

    report = check_files([record])

    assert report.is_clean is True
    assert report.findings[0].finding is Finding.INTACT
    assert "all intact" in report.describe()


def test_externally_deleted_file_is_missing(files: FileRepository, library: Path) -> None:
    record = add_file(files, library)
    Path(record.path).unlink()

    report = check_files([record])

    assert [f.finding for f in report.findings] == [Finding.MISSING]
    assert report.is_clean is False
    assert len(report.missing) == 1


def test_replaced_content_is_detected_when_verifying(files: FileRepository, library: Path) -> None:
    record = add_file(files, library)
    Path(record.path).write_bytes(b"completely different content")

    report = check_files([record], verify_content=True)

    assert [f.finding for f in report.findings] == [Finding.REPLACED]
    assert len(report.replaced) == 1


def test_same_size_replacement_needs_content_verification(
    files: FileRepository, library: Path
) -> None:
    """A same-length swap is invisible without re-hashing, which is why it is offered."""
    record = add_file(files, library)
    Path(record.path).write_bytes(b"X" * len(PAYLOAD))

    assert check_files([record]).findings[0].finding is Finding.INTACT
    assert check_files([record], verify_content=True).findings[0].finding is Finding.REPLACED


def test_existence_only_scan_does_not_read_content(
    files: FileRepository, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = add_file(files, library)
    monkeypatch.setattr(
        "fileseek.library.consistency.hash_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not hash")),
    )

    assert check_files([record]).is_clean is True


def test_offline_library_is_unreachable_not_missing(files: FileRepository, tmp_path: Path) -> None:
    """A NAS that is offline must not make every file look deleted."""
    record = FileRecord(
        id="f1",
        path=str(tmp_path / "offline-nas" / "images" / "f1.jpg"),
        filename="f1.jpg",
        media_type="image",
        size=10,
        content_hash=DIGEST,
        added_at=1_700_000_000,
    )

    report = check_files([record])

    assert [f.finding for f in report.findings] == [Finding.UNREACHABLE]
    assert report.missing == ()
    assert report.is_clean is True


def test_unreadable_file_is_unreachable(
    files: FileRepository, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = add_file(files, library)
    monkeypatch.setattr(
        "fileseek.library.consistency.hash_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("device not ready")),
    )

    report = check_files([record], verify_content=True)

    assert [f.finding for f in report.findings] == [Finding.UNREACHABLE]
    assert len(report.unreachable) == 1


def test_stat_failure_is_unreachable(
    files: FileRepository, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = add_file(files, library)
    monkeypatch.setattr(
        Path, "is_file", lambda self: (_ for _ in ()).throw(OSError("network down"))
    )

    assert check_files([record]).findings[0].finding is Finding.UNREACHABLE


def test_parent_check_failure_is_unreachable(
    files: FileRepository, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = add_file(files, library)
    Path(record.path).unlink()
    monkeypatch.setattr(Path, "is_dir", lambda self: (_ for _ in ()).throw(OSError("network down")))

    assert check_files([record]).findings[0].finding is Finding.UNREACHABLE


def test_mixed_library_reports_each_finding(files: FileRepository, library: Path) -> None:
    intact = add_file(files, library, "intact")
    gone = add_file(files, library, "gone", content_hash="hash-gone")
    changed = add_file(files, library, "changed", content_hash="hash-changed")
    Path(gone.path).unlink()

    report = check_files([intact, gone, changed], verify_content=True)

    assert report.checked == 3
    assert len(report.missing) == 1
    assert len(report.replaced) == 1
    assert "1 missing" in report.describe()
    assert "1 replaced" in report.describe()


def test_progress_is_reported_per_file(files: FileRepository, library: Path) -> None:
    records = [add_file(files, library, f"f{n}", content_hash=f"h{n}") for n in range(3)]
    seen: list[tuple[int, int]] = []

    check_files(records, on_progress=lambda done, total: seen.append((done, total)))

    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_empty_library_is_clean() -> None:
    report = check_files([])

    assert report.is_clean is True
    assert report.checked == 0


def test_finding_flags_what_needs_attention(files: FileRepository, library: Path) -> None:
    record = add_file(files, library)
    Path(record.path).unlink()

    finding = check_files([record]).findings[0]

    assert finding.needs_attention is True
    assert finding.file_id == "f1"


def test_apply_marks_missing_files(files: FileRepository, library: Path) -> None:
    record = add_file(files, library)
    Path(record.path).unlink()
    report = check_files([record])

    counts = apply_report(report, files)

    stored = files.get("f1")
    assert stored is not None
    assert stored.index_state == "missing"
    assert counts["missing"] == 1


def test_apply_queues_replaced_files_for_reindex(files: FileRepository, library: Path) -> None:
    record = add_file(files, library)
    Path(record.path).write_bytes(b"new content entirely")
    report = check_files([record], verify_content=True)

    counts = apply_report(report, files)

    stored = files.get("f1")
    assert stored is not None
    assert stored.index_state == "needs_reindex"
    assert counts["needs_reindex"] == 1


def test_apply_leaves_intact_files_alone(files: FileRepository, library: Path) -> None:
    record = add_file(files, library)

    apply_report(check_files([record], verify_content=True), files)

    stored = files.get("f1")
    assert stored is not None
    assert stored.index_state == "indexed"


def test_apply_ignores_unreachable_files(files: FileRepository, tmp_path: Path) -> None:
    """An offline NAS must not rewrite every row to missing."""
    record = FileRecord(
        id="f1",
        path=str(tmp_path / "offline" / "f1.jpg"),
        filename="f1.jpg",
        media_type="image",
        size=10,
        content_hash=DIGEST,
        added_at=1_700_000_000,
    )
    files.add(record)

    counts = apply_report(check_files([record]), files)

    stored = files.get("f1")
    assert stored is not None
    assert stored.index_state == "pending"
    assert counts == {"missing": 0, "needs_reindex": 0}


def test_apply_on_a_clean_report_changes_nothing(files: FileRepository, library: Path) -> None:
    record = add_file(files, library)

    assert apply_report(check_files([record]), files) == {"missing": 0, "needs_reindex": 0}


def test_apply_skips_rows_that_vanished(files: FileRepository, library: Path) -> None:
    record = add_file(files, library)
    Path(record.path).unlink()
    report = check_files([record])
    files.delete("f1")

    assert apply_report(report, files)["missing"] == 0


def test_scan_checks_indexed_and_pending_files(files: FileRepository, library: Path) -> None:
    add_file(files, library, "indexed-file", content_hash="h1", index_state="indexed")
    add_file(files, library, "pending-file", content_hash="h2", index_state="pending")

    report = scan_library(files)

    assert report.checked == 2


def test_scan_skips_already_missing_files(files: FileRepository, library: Path) -> None:
    add_file(files, library, "gone", content_hash="h1", index_state="missing")

    assert scan_library(files).checked == 0


def test_scan_corrects_metadata_in_one_pass(files: FileRepository, library: Path) -> None:
    record = add_file(files, library, "vanished")
    Path(record.path).unlink()

    report = scan_library(files)

    stored = files.get("vanished")
    assert stored is not None
    assert stored.index_state == "missing"
    assert len(report.missing) == 1


def test_scan_can_verify_content(files: FileRepository, library: Path) -> None:
    record = add_file(files, library, "swapped")
    Path(record.path).write_bytes(b"different bytes here")

    report = scan_library(files, verify_content=True)

    stored = files.get("swapped")
    assert stored is not None
    assert stored.index_state == "needs_reindex"
    assert report.verified_content is True


def test_scan_reports_progress(files: FileRepository, library: Path) -> None:
    add_file(files, library, "a", content_hash="h1")
    add_file(files, library, "b", content_hash="h2")
    seen: list[int] = []

    scan_library(files, on_progress=lambda done, total: seen.append(done))

    assert seen == [1, 2]


def test_scan_of_empty_library_is_clean(files: FileRepository) -> None:
    report = scan_library(files)

    assert isinstance(report, ConsistencyReport)
    assert report.is_clean is True
