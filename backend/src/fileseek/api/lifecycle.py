"""Startup and shutdown of the running service.

Shutdown has to leave the indexes loadable. Faiss holds added vectors in memory until
something writes them out, so a process that exits without saving loses every vector
added since the last save — the files on disk stay readable, but the work is gone and
the affected files silently stop matching queries.

So the sequence is fixed: stop claiming new tasks first, let whatever is in flight
finish, then write the indexes out. Saving before the in-flight work settles would
write a half-finished state and lose the rest.

A task still processing when the deadline passes is released back to `queued` rather
than failed: its file is untouched and its completed stages survive, so the next
startup resumes it instead of asking the user to re-add the file.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from fileseek.api.dependencies import Services

logger = logging.getLogger(__name__)

# How long in-flight tasks get to finish before they are released back to the queue.
# Long enough for a stage to settle, short enough that quitting from the tray feels
# immediate rather than hung.
DEFAULT_DRAIN_TIMEOUT = 10.0

# How often the drain loop re-checks. Small relative to the timeout so the common case
# — nothing in flight — returns at once.
_POLL_INTERVAL = 0.05


@dataclass
class ServiceLifecycle:
    """Whether the service is accepting work, and what shutdown has done.

    The flag here mirrors the queue's own gate: the queue is what actually refuses a
    claim, and this is what the health endpoint reports.
    """

    accepting_tasks: bool = True
    is_shutting_down: bool = False
    saved_indexes: tuple[Path, ...] = ()
    released_tasks: tuple[str, ...] = ()

    def stop_accepting(self) -> None:
        self.accepting_tasks = False
        self.is_shutting_down = True


def drain(
    services: Services,
    lifecycle: ServiceLifecycle,
    timeout: float = DEFAULT_DRAIN_TIMEOUT,
    sleep: Callable[[float], object] | None = None,
) -> tuple[str, ...]:
    """Wait for in-flight tasks, releasing whatever is still running at the deadline.

    Returns the ids of the tasks that were released, which is empty in the common
    case where everything finished on its own.

    `sleep` is injectable so a test can drive the loop without real waiting.
    """
    pause = time.sleep if sleep is None else sleep
    deadline = time.monotonic() + timeout

    while services.queue.active_count() > 0 and time.monotonic() < deadline:
        pause(_POLL_INTERVAL)

    stranded = services.queue.list_by_status("processing")
    for task in stranded:
        # Back to queued, keeping completed_stages: the next startup picks the task
        # up where it stopped rather than redoing finished stages.
        services.queue.release(task.id)

    released = tuple(task.id for task in stranded)
    lifecycle.released_tasks = released
    if released:
        logger.info("released %d in-flight task(s) back to the queue", len(released))
    return released


def save_indexes(services: Services, lifecycle: ServiceLifecycle) -> tuple[Path, ...]:
    """Write the open indexes to disk so the next startup loads them intact."""
    paths = tuple(services.context.registry.save_all())
    lifecycle.saved_indexes = paths
    logger.info("saved %d index file(s)", len(paths))
    return paths


def shutdown(
    services: Services,
    lifecycle: ServiceLifecycle,
    timeout: float = DEFAULT_DRAIN_TIMEOUT,
) -> ServiceLifecycle:
    """Stop taking work, let it settle, then persist the indexes.

    Ordering matters: saving before the drain would write a state that misses the
    vectors the in-flight task is about to add.

    A collaborator that is already gone (the database closed, the NAS unreachable)
    must not stop the process from exiting: this runs from the ASGI lifespan, which
    has no request to turn a failure into a response, so an uncaught exception here
    would crash shutdown itself rather than being reported anywhere.
    """
    lifecycle.stop_accepting()
    try:
        services.queue.stop_accepting()
        drain(services, lifecycle, timeout=timeout)
        save_indexes(services, lifecycle)
    except Exception:
        logger.exception("shutdown could not complete cleanly")
    return lifecycle
