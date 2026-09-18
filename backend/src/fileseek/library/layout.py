"""Managed library directory layout.

The library root may sit on a NAS, so writability is proven by actually writing
rather than by inspecting permission bits, which network shares report loosely.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fileseek.db.records import MediaType
from fileseek.library.mover import cleanup_orphan_parts

SUBDIRS: dict[MediaType, str] = {
    "document": "documents",
    "image": "images",
    "video": "videos",
}

THUMBNAIL_DIRNAME = ".thumbnails"

_PROBE_NAME = ".fileseek-write-probe"

_FILE_ATTRIBUTE_HIDDEN = 0x02

MAX_NAME_ATTEMPTS = 1000


class LibraryNotWritableError(OSError):
    """The chosen library root cannot be written to."""

    def __init__(self, root: Path, reason: str) -> None:
        super().__init__(f"library root is not writable: {root} ({reason})")
        self.root = root
        self.reason = reason


class NameAllocationError(RuntimeError):
    def __init__(self, target: Path) -> None:
        super().__init__(f"could not find a free name for {target} after {MAX_NAME_ATTEMPTS} tries")
        self.target = target


@dataclass(frozen=True)
class LibraryLayout:
    root: Path

    @property
    def thumbnail_dir(self) -> Path:
        return self.root / THUMBNAIL_DIRNAME

    def media_dir(self, media_type: MediaType) -> Path:
        return self.root / SUBDIRS[media_type]

    def all_dirs(self) -> tuple[Path, ...]:
        return (*(self.root / name for name in SUBDIRS.values()), self.thumbnail_dir)

    def thumbnail_path(self, relative: str) -> Path:
        return self.thumbnail_dir / relative

    def relative_to_root(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def contains(self, path: Path) -> bool:
        """True when path is inside the library, used to reject traversal."""
        try:
            resolved_root = self.root.resolve()
            resolved = path.resolve()
        except OSError:
            return False
        return resolved == resolved_root or resolved_root in resolved.parents

    def verify_writable(self) -> None:
        probe = self.root / _PROBE_NAME
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            with probe.open("wb") as handle:
                handle.write(b"probe")
        except OSError as error:
            raise LibraryNotWritableError(self.root, str(error)) from error
        finally:
            probe.unlink(missing_ok=True)

    def initialize(self) -> LibraryLayout:
        """Create the per-type subdirectories, refusing an unwritable root.

        Runs at every library open, which is also the moment to sweep away
        temporary files left by a move that a crash or power loss cut short.
        """
        self.verify_writable()
        for directory in self.all_dirs():
            directory.mkdir(parents=True, exist_ok=True)
        self._hide_thumbnail_dir()
        self.cleanup_interrupted_moves()
        return self

    def cleanup_interrupted_moves(self) -> list[Path]:
        """Delete `.fileseek-part` leftovers, returning what was removed."""
        return cleanup_orphan_parts(*self.all_dirs())

    def _hide_thumbnail_dir(self) -> None:
        # The dot prefix hides it on POSIX; Windows needs the attribute set.
        import ctypes

        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return
        windll.kernel32.SetFileAttributesW(str(self.thumbnail_dir), _FILE_ATTRIBUTE_HIDDEN)

    def allocate_path(self, media_type: MediaType, filename: str) -> Path:
        """Pick a free path for filename, suffixing `-2`, `-3`, ... on collision.

        Only called once the content hash has ruled out a true duplicate, so a
        collision here means different content sharing a name.
        """
        directory = self.media_dir(media_type)
        candidate = directory / filename
        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        for counter in range(2, MAX_NAME_ATTEMPTS + 2):
            candidate = directory / f"{stem}-{counter}{suffix}"
            if not candidate.exists():
                return candidate
        raise NameAllocationError(directory / filename)
