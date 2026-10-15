from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from watchfiles import Change, awatch

from fileseek.config.settings import Settings
from fileseek.features.library.application.commands import AddFileCommand
from fileseek.features.library.application.ports import (
    FolderSourceRootPort,
    WatchableSourceRoot,
)
from fileseek.features.library.application.use_cases.add_file import AddFileUseCase
from fileseek.features.library.domain.entities import (
    FolderSourceBinding,
    FolderSourceSeen,
)
from fileseek.features.library.domain.exceptions import SourceUnavailableError
from fileseek.features.library.domain.repositories import (
    FolderSourceBindingRepository,
    FolderSourceSeenRepository,
)
from fileseek.shared.domain.exceptions import (
    FileAlreadyExistsError,
    FileNotSupportError,
)
from fileseek.shared.domain.identifiers import generate_id

logger = logging.getLogger(__name__)

type FileChangeSet = set[tuple[int, str]]
type WatchStreamFactory = Callable[
    [Path, bool, asyncio.Event],
    AsyncIterable[FileChangeSet],
]
type StabilityState = Literal["stable", "unstable", "missing"]


async def watchfiles_stream(
    filesystem_path: Path,
    recursive: bool,
    stop_event: asyncio.Event,
) -> AsyncIterable[FileChangeSet]:
    async for changes in awatch(
        filesystem_path,
        recursive=recursive,
        stop_event=stop_event,
    ):
        yield {(int(change), str(path)) for change, path in changes}


@dataclass
class _WatchCandidate:
    binding: FolderSourceBinding
    root: WatchableSourceRoot
    source_path: str
    filesystem_path: Path
    attempts: int = 0


class FolderSourceWatcherService:
    def __init__(
        self,
        *,
        binding_repo: FolderSourceBindingRepository,
        seen_repo: FolderSourceSeenRepository,
        root_resolver: FolderSourceRootPort,
        add_file_use_case: AddFileUseCase,
        settings: Settings,
        stream_factory: WatchStreamFactory | None = None,
    ) -> None:
        self.binding_repo = binding_repo
        self.seen_repo = seen_repo
        self.root_resolver = root_resolver
        self.add_file_use_case = add_file_use_case
        self.settings = settings
        self.stream_factory = stream_factory or watchfiles_stream
        self._running = False
        self._stop_event = asyncio.Event()
        self._binding_tasks: dict[str, asyncio.Task[None]] = {}
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._periodic_scan_task: asyncio.Task[None] | None = None
        self._stability_retry_tasks: set[asyncio.Task[None]] = set()
        self._queue: asyncio.Queue[_WatchCandidate | None] = asyncio.Queue()

    @property
    def running(self) -> bool:
        return self._running

    def watching_binding_ids(self) -> set[str]:
        return {binding_id for binding_id, task in self._binding_tasks.items() if not task.done()}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event = asyncio.Event()
        self._queue = asyncio.Queue()
        self._worker_tasks = [
            asyncio.create_task(self._run_worker())
            for _ in range(self.settings.folder_watch_worker_count)
        ]
        if self.settings.folder_watch_scan_interval_seconds > 0:
            self._periodic_scan_task = asyncio.create_task(self._run_periodic_scans())
        await self.reconcile()

    async def stop(self, timeout: float | None = None) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._periodic_scan_task is not None:
            self._periodic_scan_task.cancel()
        for retry_task in self._stability_retry_tasks:
            retry_task.cancel()
        tasks = (
            list(self._binding_tasks.values())
            + list(self._worker_tasks)
            + [task for task in (self._periodic_scan_task,) if task is not None]
            + list(self._stability_retry_tasks)
        )
        for _ in self._worker_tasks:
            self._queue.put_nowait(None)
        done, pending = await asyncio.wait(
            tasks,
            timeout=self.settings.task_drain_timeout if timeout is None else timeout,
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._binding_tasks.clear()
        self._worker_tasks.clear()
        self._periodic_scan_task = None
        self._stability_retry_tasks.clear()
        for task in done:
            if task.cancelled():
                continue
            if task.exception() is not None:
                logger.warning("文件夹来源监听任务退出异常", exc_info=task.exception())

    async def reconcile(self) -> None:
        bindings = await self.binding_repo.list_enabled()
        enabled_ids = {binding.id for binding in bindings}
        for binding_id in set(self._binding_tasks) - enabled_ids:
            await self._stop_binding_task(binding_id)
        for binding in bindings:
            if binding.id not in self._binding_tasks or self._binding_tasks[binding.id].done():
                await self._start_binding_task(binding)

    async def _run_periodic_scans(self) -> None:
        while self._running:
            await asyncio.sleep(self.settings.folder_watch_scan_interval_seconds)
            if not self._running:
                return
            try:
                await self.reconcile()
                await self._scan_enabled_bindings()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("文件夹来源周期扫描失败", exc_info=exc)

    async def _scan_enabled_bindings(self) -> None:
        for binding in await self.binding_repo.list_enabled():
            if not self._running:
                return
            try:
                root = await self.root_resolver.resolve(
                    binding.storage_id,
                    binding.source_path,
                )
                seen_paths = await self.seen_repo.list_paths(binding.id)
                await self._enqueue_unseen_paths(binding, root, seen_paths)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._mark_binding(
                    binding,
                    "unavailable" if isinstance(exc, SourceUnavailableError) else "error",
                    str(exc),
                )

    async def reload_binding(self, binding_id: str) -> None:
        await self._stop_binding_task(binding_id)
        if not self._running:
            return
        binding = await self.binding_repo.get_by_id(binding_id)
        if binding is not None and binding.enabled:
            await self._start_binding_task(binding)

    async def remove_binding(self, binding_id: str) -> None:
        await self._stop_binding_task(binding_id)

    async def _start_binding_task(self, binding: FolderSourceBinding) -> None:
        task = asyncio.create_task(self._run_binding(binding))
        self._binding_tasks[binding.id] = task

    async def _stop_binding_task(self, binding_id: str) -> None:
        task = self._binding_tasks.pop(binding_id, None)
        if task is None or task.done():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _run_binding(self, binding: FolderSourceBinding) -> None:
        try:
            root = await self.root_resolver.resolve(
                binding.storage_id,
                binding.source_path,
            )
        except Exception as exc:
            await self._mark_binding(binding, "unavailable", str(exc))
            return

        binding.mark_watching()
        await self.binding_repo.save(binding)
        try:
            seen_paths = await self.seen_repo.list_paths(binding.id)
            await self._enqueue_unseen_paths(binding, root, seen_paths)
            stream = self.stream_factory(
                root.filesystem_path,
                binding.recursive,
                self._stop_event,
            )
            async for changes in stream:
                for change, raw_path in changes:
                    await self._handle_change(binding, root, change, Path(raw_path))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._mark_binding(binding, "error", str(exc))

    async def _enqueue_unseen_paths(
        self,
        binding: FolderSourceBinding,
        root: WatchableSourceRoot,
        seen_paths: set[str],
    ) -> None:
        for source_path in await self.root_resolver.list_file_paths(
            root,
            recursive=binding.recursive,
        ):
            if source_path not in seen_paths:
                await self._enqueue_candidate(binding, root, source_path)

    async def _handle_change(
        self,
        binding: FolderSourceBinding,
        root: WatchableSourceRoot,
        change: int,
        filesystem_path: Path,
    ) -> None:
        if not binding.recursive and filesystem_path.parent != root.filesystem_path:
            return

        source_path = self._source_path(root, filesystem_path)
        if change == int(Change.deleted):
            await self.seen_repo.delete_path(binding.id, source_path)
            return

        if change not in {int(Change.added), int(Change.modified)}:
            return
        if not self._is_processable_file(filesystem_path):
            return
        seen_paths = await self.seen_repo.list_paths(binding.id)
        if source_path in seen_paths:
            return
        await self._enqueue_candidate(binding, root, source_path)

    @staticmethod
    def _is_processable_file(filesystem_path: Path) -> bool:
        if not filesystem_path.is_file():
            return False
        name = filesystem_path.name
        if name.startswith(".") or name.startswith("~$"):
            return False
        return not name.endswith((".part", ".crdownload", ".download", ".tmp"))

    @staticmethod
    def _source_path(root: WatchableSourceRoot, filesystem_path: Path) -> str:
        if root.source_path.startswith("/"):
            return filesystem_path.as_posix()
        return filesystem_path.relative_to(root.storage_root).as_posix()

    async def _enqueue_candidate(
        self,
        binding: FolderSourceBinding,
        root: WatchableSourceRoot,
        source_path: str,
    ) -> None:
        await self.seen_repo.save(_seen_entry(binding.id, source_path, outcome="pending"))
        await self._queue.put(
            _WatchCandidate(
                binding=binding,
                root=root,
                source_path=source_path,
                filesystem_path=root.storage_root / source_path
                if not root.source_path.startswith("/")
                else Path(source_path),
            )
        )

    async def _run_worker(self) -> None:
        while self._running or not self._queue.empty():
            candidate = await self._queue.get()
            if candidate is None:
                self._queue.task_done()
                return
            try:
                await self._process_candidate(candidate)
            finally:
                self._queue.task_done()

    async def _process_candidate(self, candidate: _WatchCandidate) -> None:
        stability = await self._stability(candidate.filesystem_path)
        if stability == "unstable":
            self._schedule_stability_retry(candidate)
            return
        if stability == "missing":
            await self.seen_repo.save(
                _seen_entry(candidate.binding.id, candidate.source_path, outcome="missing")
            )
            return
        try:
            result = await self.add_file_use_case.execute(
                AddFileCommand(
                    folder_id=candidate.binding.folder_id,
                    path=candidate.source_path,
                    storage_id=candidate.binding.storage_id,
                )
            )
            _ = result.file_id
            await self.seen_repo.save(
                _seen_entry(
                    candidate.binding.id,
                    candidate.source_path,
                    outcome="imported",
                )
            )
        except FileAlreadyExistsError:
            await self.seen_repo.save(
                _seen_entry(
                    candidate.binding.id,
                    candidate.source_path,
                    outcome="duplicate",
                )
            )
        except FileNotSupportError as exc:
            await self._mark_binding(candidate.binding, "error", str(exc))
            await self.seen_repo.save(
                _seen_entry(
                    candidate.binding.id,
                    candidate.source_path,
                    outcome="unsupported",
                )
            )
        except (SourceUnavailableError, OSError) as exc:
            if candidate.attempts < self.settings.folder_watch_max_retries:
                await asyncio.sleep(min(0.1 * (2**candidate.attempts), 5.0))
                await self._queue.put(
                    _WatchCandidate(
                        binding=candidate.binding,
                        root=candidate.root,
                        source_path=candidate.source_path,
                        filesystem_path=candidate.filesystem_path,
                        attempts=candidate.attempts + 1,
                    )
                )
                return
            await self._mark_binding(candidate.binding, "error", str(exc))
            await self.seen_repo.save(
                _seen_entry(
                    candidate.binding.id,
                    candidate.source_path,
                    outcome="failed",
                )
            )
        except Exception as exc:
            await self._mark_binding(candidate.binding, "error", str(exc))
            await self.seen_repo.save(
                _seen_entry(
                    candidate.binding.id,
                    candidate.source_path,
                    outcome="failed",
                )
            )

    async def _is_stable(self, filesystem_path: Path) -> bool:
        return await self._stability(filesystem_path) == "stable"

    async def _stability(self, filesystem_path: Path) -> StabilityState:
        try:
            previous = self._stat(filesystem_path)
            if previous is None:
                return "missing"
            for _ in range(self.settings.folder_watch_stable_checks):
                await asyncio.sleep(self.settings.folder_watch_settle_seconds)
                current = self._stat(filesystem_path)
                if current is None:
                    return "missing"
                if current != previous:
                    return "unstable"
                previous = current
        except OSError:
            return "missing"
        return "stable"

    def _schedule_stability_retry(self, candidate: _WatchCandidate) -> None:
        retry_delay = max(self.settings.folder_watch_settle_seconds, 0.1)

        async def retry() -> None:
            await asyncio.sleep(retry_delay)
            await self._queue.put(candidate)

        task = asyncio.create_task(retry())
        self._stability_retry_tasks.add(task)
        task.add_done_callback(self._stability_retry_tasks.discard)

    @staticmethod
    def _stat(filesystem_path: Path) -> tuple[int, int] | None:
        if not filesystem_path.exists() or not filesystem_path.is_file():
            return None
        metadata = filesystem_path.stat()
        return metadata.st_size, metadata.st_mtime_ns

    async def _mark_binding(
        self,
        binding: FolderSourceBinding,
        status: str,
        message: str,
    ) -> None:
        if status == "unavailable":
            binding.mark_unavailable()
        else:
            binding.mark_error(message)
        await self.binding_repo.save(binding)


def _seen_entry(
    binding_id: str,
    source_path: str,
    *,
    outcome: str,
) -> FolderSourceSeen:
    return FolderSourceSeen(
        id=generate_id("fss"),
        binding_id=binding_id,
        source_path=source_path,
        outcome=outcome,
    )
