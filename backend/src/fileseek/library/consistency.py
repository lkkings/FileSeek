"""Detects library files changed or removed outside FileSeek.

The library is the only real source of truth: indexes and metadata can be rebuilt
from it, but not the reverse. So when a file disappears or is replaced behind our
back, the metadata is corrected rather than trusted.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from fileseek.db.records import FileRecord
from fileseek.db.repositories import FileRepository
from fileseek.library.hashing import CHUNK_SIZE, hash_file


class Finding(Enum):
    INTACT = "intact"
    MISSING = "missing"
    REPLACED = "replaced"
    # The library sits on a NAS that may be offline; an unreachable file is not
    # the same as a deleted one, so it must never be marked missing.
    UNREACHABLE = "unreachable"


@dataclass(frozen=True)
class FileFinding:
    file_id: str
    path: Path
    finding: Finding

    @property
    def needs_attention(self) -> bool:
        return self.finding in (Finding.MISSING, Finding.REPLACED)


@dataclass(frozen=True)
class ConsistencyReport:
    findings: tuple[FileFinding, ...]
    checked: int
    verified_content: bool

    @property
    def missing(self) -> tuple[FileFinding, ...]:
        return tuple(f for f in self.findings if f.finding is Finding.MISSING)

    @property
    def replaced(self) -> tuple[FileFinding, ...]:
        return tuple(f for f in self.findings if f.finding is Finding.REPLACED)

    @property
    def unreachable(self) -> tuple[FileFinding, ...]:
        return tuple(f for f in self.findings if f.finding is Finding.UNREACHABLE)

    @property
    def is_clean(self) -> bool:
        return not any(f.needs_attention for f in self.findings)

    def describe(self) -> str:
        if self.is_clean:
            return f"checked {self.checked} files, all intact"
        parts = []
        if self.missing:
            parts.append(f"{len(self.missing)} missing")
        if self.replaced:
            parts.append(f"{len(self.replaced)} replaced")
        return f"checked {self.checked} files: {', '.join(parts)}"


def _classify(record: FileRecord, verify_content: bool, chunk_size: int) -> Finding:
    path = Path(record.path)
    try:
        exists = path.is_file()
    except OSError:
        return Finding.UNREACHABLE

    if not exists:
        # Distinguish a deleted file from a whole library that is offline: if the
        # parent directory is gone too, the storage is unreachable, not the file.
        try:
            if not path.parent.is_dir():
                return Finding.UNREACHABLE
        except OSError:
            return Finding.UNREACHABLE
        return Finding.MISSING

    if not verify_content:
        return Finding.INTACT

    try:
        digest = hash_file(path, chunk_size)
    except OSError:
        return Finding.UNREACHABLE

    return Finding.INTACT if digest == record.content_hash else Finding.REPLACED


def check_files(
    records: Sequence[FileRecord],
    verify_content: bool = False,
    chunk_size: int = CHUNK_SIZE,
    on_progress: Callable[[int, int], None] | None = None,
) -> ConsistencyReport:
    """Classify each record against what is actually on disk.

    Existence alone is cheap; `verify_content` re-hashes every file, which is the
    only way to notice a same-size replacement but costs a full read.
    """
    findings: list[FileFinding] = []
    for position, record in enumerate(records, start=1):
        findings.append(
            FileFinding(
                file_id=record.id,
                path=Path(record.path),
                finding=_classify(record, verify_content, chunk_size),
            )
        )
        if on_progress is not None:
            on_progress(position, len(records))

    return ConsistencyReport(
        findings=tuple(findings), checked=len(records), verified_content=verify_content
    )


def apply_report(report: ConsistencyReport, files: FileRepository) -> dict[str, int]:
    """Record what the scan found, so search stops offering unusable results.

    A replaced file keeps its row and is queued for reindexing; its old vectors no
    longer describe its content.
    """
    counts = {"missing": 0, "needs_reindex": 0}
    for finding in report.missing:
        if files.set_index_state(finding.file_id, "missing"):
            counts["missing"] += 1
    for finding in report.replaced:
        if files.set_index_state(finding.file_id, "needs_reindex"):
            counts["needs_reindex"] += 1
    return counts


def scan_library(
    files: FileRepository,
    verify_content: bool = False,
    chunk_size: int = CHUNK_SIZE,
    on_progress: Callable[[int, int], None] | None = None,
) -> ConsistencyReport:
    """Check every indexed file and correct the metadata in one pass."""
    records = [
        *files.list_by_index_state("indexed"),
        *files.list_by_index_state("pending"),
    ]
    report = check_files(records, verify_content, chunk_size, on_progress)
    apply_report(report, files)
    return report
