from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from fileseek.features.library.application.commands import (
    AddFileCommand,
    BatchImportCommand,
)
from fileseek.features.library.application.dto import (
    BatchImportStartedDTO,
    ImportEventDTO,
)
from fileseek.features.library.application.use_cases.add_file import AddFileUseCase
from fileseek.shared.domain.exceptions import ApplicationError

logger = logging.getLogger(__name__)


@dataclass
class _ImportSession:
    import_id: str
    command: BatchImportCommand
    events: list[ImportEventDTO] = field(default_factory=list)
    subscribers: set[asyncio.Queue[ImportEventDTO]] = field(default_factory=set)
    runner: asyncio.Task[None] | None = None
    completed_at: float | None = None
    next_event_id: int = 1


class BatchImportSessionManager:
    def __init__(
        self,
        add_file_use_case: AddFileUseCase,
        *,
        session_retention_seconds: float = 300,
    ) -> None:
        self.add_file_use_case = add_file_use_case
        self.session_retention_seconds = session_retention_seconds
        self._sessions: dict[str, _ImportSession] = {}

    async def start(self, command: BatchImportCommand) -> BatchImportStartedDTO:
        self._remove_expired_sessions()
        import_id = f"import_{time.monotonic_ns():x}"
        session = _ImportSession(import_id=import_id, command=command)
        self._sessions[import_id] = session
        session.runner = asyncio.create_task(self._run_session(session))
        return BatchImportStartedDTO(import_id=import_id, total=len(command.items))

    async def subscribe(
        self,
        import_id: str,
        last_event_id: int = 0,
    ):
        session = self._sessions.get(import_id)
        if session is None:
            raise KeyError(import_id)

        queue: asyncio.Queue[ImportEventDTO] = asyncio.Queue()
        replayed = False
        for event in session.events:
            if event.id > last_event_id:
                queue.put_nowait(event)
                replayed = True

        if not replayed and session.completed_at is not None:
            return

        session.subscribers.add(queue)
        try:
            while True:
                event = await queue.get()
                yield event
                if event.type == "batch_completed":
                    break
        finally:
            session.subscribers.discard(queue)

    async def close(self) -> None:
        runners = [
            session.runner
            for session in self._sessions.values()
            if session.runner is not None and not session.runner.done()
        ]
        for runner in runners:
            runner.cancel()
        if runners:
            await asyncio.gather(*runners, return_exceptions=True)
        self._sessions.clear()

    def _remove_expired_sessions(self) -> None:
        now = time.monotonic()
        expired = [
            import_id
            for import_id, session in self._sessions.items()
            if session.completed_at is not None
            and now - session.completed_at > self.session_retention_seconds
        ]
        for import_id in expired:
            session = self._sessions.pop(import_id)
            if session.runner is not None and not session.runner.done():
                session.runner.cancel()

    async def _run_session(self, session: _ImportSession) -> None:
        succeeded = 0
        failed = 0
        self._emit(session, "batch_started", {"total": len(session.command.items)})
        try:
            for index, item in enumerate(session.command.items):
                self._emit(
                    session,
                    "item_started",
                    {
                        "index": index,
                        "path": item.path,
                        "storage_id": item.storage_id,
                    },
                )
                try:
                    result = await self.add_file_use_case.execute(
                        AddFileCommand(
                            folder_id=session.command.folder_id,
                            path=item.path,
                            storage_id=item.storage_id,
                        )
                    )
                    self._emit(
                        session,
                        "item_registered",
                        {
                            "index": index,
                            "file_id": result.file_id,
                            "task_id": result.task_id,
                        },
                    )
                    succeeded += 1
                    self._emit(
                        session,
                        "item_completed",
                        {
                            "index": index,
                            "file_id": result.file_id,
                            "task_id": result.task_id,
                        },
                    )
                except ApplicationError as exc:
                    failed += 1
                    self._emit(
                        session,
                        "item_failed",
                        self._failure_payload(index, item, str(exc)),
                    )
                except Exception:
                    logger.exception("批量导入项失败: %s", item.path)
                    failed += 1
                    self._emit(
                        session,
                        "item_failed",
                        self._failure_payload(index, item, "导入失败"),
                    )
        except Exception:
            logger.exception("批量导入会话失败: %s", session.import_id)
            self._emit(
                session,
                "batch_failed",
                {"total": len(session.command.items), "succeeded": succeeded, "failed": failed},
            )
        else:
            self._emit(
                session,
                "batch_completed",
                {
                    "total": len(session.command.items),
                    "succeeded": succeeded,
                    "failed": failed,
                },
            )
        finally:
            session.completed_at = time.monotonic()

    @staticmethod
    def _failure_payload(
        index: int,
        item,
        error: str | None,
    ) -> dict[str, object]:
        return {
            "index": index,
            "path": item.path,
            "storage_id": item.storage_id,
            "error": error or "导入失败",
        }

    def _emit(
        self,
        session: _ImportSession,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        event = ImportEventDTO(
            id=session.next_event_id,
            type=event_type,
            payload=payload,
        )
        session.next_event_id += 1
        session.events.append(event)
        for subscriber in session.subscribers:
            subscriber.put_nowait(event)
