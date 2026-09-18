import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from fileseek.db import connect, migrate
from fileseek.tasks import (
    IllegalTransitionError,
    ProgressRegressionError,
    TaskNotFoundError,
    TaskQueue,
)
from fileseek.tasks.records import PRIORITY_BATCH, PRIORITY_INTERACTIVE, STAGE_ORDER


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def queue(db: sqlite3.Connection) -> TaskQueue:
    return TaskQueue(db)


def insert_file(connection: sqlite3.Connection, file_id: str = "f1") -> str:
    connection.execute(
        "INSERT INTO files (id, path, filename, media_type, size, content_hash, added_at) "
        "VALUES (?, ?, ?, 'image', 10, ?, 1700000000)",
        (file_id, f"/library/images/{file_id}.jpg", f"{file_id}.jpg", f"hash-{file_id}"),
    )
    return file_id


class InterceptingConnection:
    """Wraps a connection so one statement can be hooked.

    Patching sqlite3.Connection.execute globally breaks fixture teardown, so the
    interception is scoped to the instance the queue under test holds.
    """

    def __init__(self, connection: sqlite3.Connection, prefix: str, hook: object) -> None:
        self._connection = connection
        self._prefix = prefix
        self._hook = hook

    def execute(self, sql: str, *args: object) -> sqlite3.Cursor:
        if sql.lstrip().startswith(self._prefix):
            self._hook(self._connection)  # type: ignore[operator]
        return self._connection.execute(sql, *args)


def test_enqueue_starts_queued_at_zero(queue: TaskQueue) -> None:
    task = queue.enqueue("D:/downloads/cat.jpg", media_type="image")

    assert task.status == "queued"
    assert task.progress == 0
    assert task.media_type == "image"
    assert task.completed_stages == ()


def test_enqueue_assigns_unique_ids(queue: TaskQueue) -> None:
    first = queue.enqueue("a.jpg")
    second = queue.enqueue("b.jpg")

    assert first.id != second.id


def test_enqueue_many_creates_one_task_per_path(queue: TaskQueue) -> None:
    tasks = queue.enqueue_many(["a.jpg", "b.png", "c.mp4"])

    assert len(tasks) == 3
    assert [task.source_path for task in tasks] == ["a.jpg", "b.png", "c.mp4"]


def test_interactive_submission_gets_higher_priority(queue: TaskQueue) -> None:
    batch = queue.enqueue("bulk.jpg")
    interactive = queue.enqueue("clicked.jpg", interactive=True)

    assert batch.priority == PRIORITY_BATCH
    assert interactive.priority == PRIORITY_INTERACTIVE
    assert interactive.is_interactive is True


def test_get_unknown_task_raises(queue: TaskQueue) -> None:
    with pytest.raises(TaskNotFoundError, match="no such task"):
        queue.get("ghost")


def test_find_unknown_task_returns_none(queue: TaskQueue) -> None:
    assert queue.find("ghost") is None


def test_find_returns_existing_task(queue: TaskQueue) -> None:
    task = queue.enqueue("a.jpg")

    assert queue.find(task.id) == task


def test_claim_takes_the_oldest_queued_task(queue: TaskQueue) -> None:
    first = queue.enqueue("first.jpg", created_at=1_700_000_000)
    queue.enqueue("second.jpg", created_at=1_700_000_100)

    claimed = queue.claim_next()

    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status == "processing"
    assert claimed.started_at is not None


def test_claim_prefers_interactive_over_older_batch(queue: TaskQueue) -> None:
    queue.enqueue("bulk-1.jpg", created_at=1_700_000_000)
    queue.enqueue("bulk-2.jpg", created_at=1_700_000_001)
    clicked = queue.enqueue("clicked.jpg", interactive=True, created_at=1_700_000_500)

    claimed = queue.claim_next()

    assert claimed is not None
    assert claimed.id == clicked.id


def test_bulk_import_does_not_starve_a_later_click(db: sqlite3.Connection) -> None:
    """A click during a 200-file import waits for the running task, not the queue."""
    queue = TaskQueue(db, max_concurrent=1)
    queue.enqueue_many([f"bulk-{n}.jpg" for n in range(200)])
    in_flight = queue.claim_next()
    assert in_flight is not None

    clicked = queue.enqueue("clicked.jpg", interactive=True)
    queue.mark_completed(in_flight.id)
    next_up = queue.claim_next()

    assert next_up is not None
    assert next_up.id == clicked.id


def test_claim_returns_none_when_queue_is_empty(queue: TaskQueue) -> None:
    assert queue.claim_next() is None


def test_claim_returns_none_at_concurrency_cap(db: sqlite3.Connection) -> None:
    queue = TaskQueue(db, max_concurrent=2)
    queue.enqueue_many(["a.jpg", "b.jpg", "c.jpg"])

    assert queue.claim_next() is not None
    assert queue.claim_next() is not None
    assert queue.claim_next() is None
    assert queue.active_count() == 2


def test_concurrency_cap_holds_across_many_submissions(db: sqlite3.Connection) -> None:
    queue = TaskQueue(db, max_concurrent=3)
    queue.enqueue_many([f"v{n}.mp4" for n in range(50)])

    while queue.claim_next() is not None:
        pass

    assert queue.active_count() == 3
    assert len(queue.list_by_status("queued")) == 47


def test_capacity_frees_up_after_completion(db: sqlite3.Connection) -> None:
    queue = TaskQueue(db, max_concurrent=1)
    queue.enqueue_many(["a.jpg", "b.jpg"])
    first = queue.claim_next()
    assert first is not None

    assert queue.claim_next() is None
    queue.mark_completed(first.id)

    assert queue.claim_next() is not None


def test_max_concurrent_must_be_positive(db: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        TaskQueue(db, max_concurrent=0)


def test_two_connections_never_claim_the_same_task(tmp_path: Path) -> None:
    """The claim must be atomic, so two workers cannot pick up one task."""
    database = tmp_path / "metadata.db"
    with connect(database) as first_connection:
        migrate(first_connection)

    left = connect(database)
    right = connect(database)
    try:
        TaskQueue(left).enqueue_many(["a.jpg", "b.jpg"])

        first = TaskQueue(left).claim_next()
        second = TaskQueue(right).claim_next()

        assert first is not None
        assert second is not None
        assert first.id != second.id
    finally:
        left.close()
        right.close()


def test_claim_skips_a_task_taken_between_select_and_update(db: sqlite3.Connection) -> None:
    task = TaskQueue(db).enqueue("a.jpg")

    def steal(connection: sqlite3.Connection) -> None:
        connection.execute("UPDATE tasks SET status = 'processing' WHERE id = ?", (task.id,))

    racing = InterceptingConnection(db, "UPDATE tasks SET status = 'processing'", steal)

    assert TaskQueue(racing).claim_next() is None  # type: ignore[arg-type]


def test_claim_rolls_back_on_error(db: sqlite3.Connection) -> None:
    queue = TaskQueue(db)
    queue.enqueue("a.jpg")

    def explode(connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("boom")

    failing = InterceptingConnection(db, "UPDATE tasks SET status = 'processing'", explode)

    with pytest.raises(sqlite3.OperationalError, match="boom"):
        TaskQueue(failing).claim_next()  # type: ignore[arg-type]

    assert len(queue.list_by_status("queued")) == 1


def test_progress_moves_forward(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")
    queue.claim_next()

    updated = queue.report_progress(task.id, 25, stage="extracted")

    assert updated.progress == 25
    assert updated.stage == "extracted"


def test_progress_sequence_is_monotonic(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")
    queue.claim_next()

    seen = [queue.report_progress(task.id, value).progress for value in (5, 20, 20, 80, 100)]

    assert seen == sorted(seen)


def test_progress_may_not_regress(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")
    queue.claim_next()
    queue.report_progress(task.id, 50)

    with pytest.raises(ProgressRegressionError, match="backwards"):
        queue.report_progress(task.id, 20)


@pytest.mark.parametrize("value", [-1, 101])
def test_progress_outside_range_is_rejected(queue: TaskQueue, value: int) -> None:
    task = queue.enqueue("clip.mp4")

    with pytest.raises(ValueError, match="between 0 and 100"):
        queue.report_progress(task.id, value)


def test_progress_keeps_previous_stage_when_omitted(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")
    queue.report_progress(task.id, 10, stage="moved")

    updated = queue.report_progress(task.id, 20)

    assert updated.stage == "moved"


def test_completed_stages_accumulate(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")

    queue.complete_stage(task.id, "moved")
    updated = queue.complete_stage(task.id, "extracted")

    assert updated.completed_stages == ("moved", "extracted")
    assert updated.next_stage() == "encoded"


def test_completing_a_stage_twice_is_a_no_op(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")
    queue.complete_stage(task.id, "moved")

    updated = queue.complete_stage(task.id, "moved")

    assert updated.completed_stages == ("moved",)


def test_mark_completed_sets_full_progress(queue: TaskQueue, db: sqlite3.Connection) -> None:
    file_id = insert_file(db)
    task = queue.enqueue("cat.jpg")
    queue.claim_next()

    completed = queue.mark_completed(task.id, file_id=file_id)

    assert completed.status == "completed"
    assert completed.progress == 100
    assert completed.file_id == file_id
    assert completed.completed_at is not None


def test_mark_failed_records_the_reason(queue: TaskQueue) -> None:
    task = queue.enqueue("broken.mp4")
    queue.claim_next()

    failed = queue.mark_failed(task.id, "could not decode video")

    assert failed.status == "failed"
    assert failed.error_message == "could not decode video"


def test_completing_an_unclaimed_task_is_rejected(queue: TaskQueue) -> None:
    task = queue.enqueue("cat.jpg")

    with pytest.raises(IllegalTransitionError):
        queue.mark_completed(task.id)


def test_retry_requeues_a_failed_task(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")
    queue.claim_next()
    queue.mark_failed(task.id, "NAS unreachable")

    retried = queue.retry(task.id)

    assert retried.status == "queued"
    assert retried.error_message is None
    assert retried.started_at is None


def test_retry_preserves_completed_stages(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")
    queue.claim_next()
    queue.complete_stage(task.id, "moved")
    queue.complete_stage(task.id, "extracted")
    queue.mark_failed(task.id, "index write failed")

    retried = queue.retry(task.id)

    assert retried.completed_stages == ("moved", "extracted")
    assert retried.next_stage() == "encoded"


def test_retried_task_can_be_claimed_again(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")
    queue.claim_next()
    queue.mark_failed(task.id, "transient")
    queue.retry(task.id)

    claimed = queue.claim_next()

    assert claimed is not None
    assert claimed.id == task.id


def test_retrying_a_completed_task_is_rejected(queue: TaskQueue) -> None:
    task = queue.enqueue("cat.jpg")
    queue.claim_next()
    queue.mark_completed(task.id)

    with pytest.raises(IllegalTransitionError):
        queue.retry(task.id)


def test_release_returns_an_in_flight_task_to_the_queue(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")
    queue.claim_next()
    queue.complete_stage(task.id, "moved")

    released = queue.release(task.id)

    assert released.status == "queued"
    assert released.completed_stages == ("moved",)
    assert released.error_message is None


def test_recover_interrupted_requeues_in_flight_tasks(queue: TaskQueue) -> None:
    first = queue.enqueue("a.mp4")
    queue.enqueue("b.mp4")
    queue.claim_next()
    queue.complete_stage(first.id, "moved")

    recovered = queue.recover_interrupted()

    assert recovered == 1
    assert len(queue.list_by_status("queued")) == 2
    assert queue.get(first.id).completed_stages == ("moved",)


def test_recover_leaves_finished_tasks_alone(queue: TaskQueue) -> None:
    task = queue.enqueue("a.jpg")
    queue.claim_next()
    queue.mark_completed(task.id)

    assert queue.recover_interrupted() == 0
    assert queue.get(task.id).status == "completed"


def test_queued_tasks_survive_a_reopen(tmp_path: Path) -> None:
    database = tmp_path / "metadata.db"
    with connect(database) as connection:
        migrate(connection)
        TaskQueue(connection).enqueue_many(["a.jpg", "b.mp4"])

    with connect(database) as connection:
        queue = TaskQueue(connection)

        assert len(queue.list_by_status("queued")) == 2


def test_in_flight_work_resumes_after_restart(tmp_path: Path) -> None:
    database = tmp_path / "metadata.db"
    with connect(database) as connection:
        migrate(connection)
        queue = TaskQueue(connection)
        task = queue.enqueue("clip.mp4")
        queue.claim_next()
        queue.complete_stage(task.id, "moved")
        queue.complete_stage(task.id, "extracted")

    with connect(database) as connection:
        queue = TaskQueue(connection)
        assert queue.recover_interrupted() == 1

        resumed = queue.claim_next()
        assert resumed is not None
        assert resumed.next_stage() == "encoded"


def test_list_by_status_orders_by_priority(queue: TaskQueue) -> None:
    queue.enqueue("bulk.jpg", created_at=1_700_000_000)
    clicked = queue.enqueue("clicked.jpg", interactive=True, created_at=1_700_000_100)

    listed = queue.list_by_status("queued")

    assert listed[0].id == clicked.id


def test_purge_removes_only_old_completed_tasks(queue: TaskQueue) -> None:
    stale = queue.enqueue("old.jpg")
    queue.claim_next()
    queue.mark_completed(stale.id)
    queue.enqueue("pending.jpg")

    removed = queue.purge_completed(older_than=9_999_999_999)

    assert removed == 1
    assert queue.find(stale.id) is None
    assert len(queue.list_by_status("queued")) == 1


def test_purge_keeps_recent_completed_tasks(queue: TaskQueue) -> None:
    task = queue.enqueue("recent.jpg")
    queue.claim_next()
    queue.mark_completed(task.id)

    assert queue.purge_completed(older_than=1) == 0
    assert queue.find(task.id) is not None


def test_all_stages_can_be_recorded(queue: TaskQueue) -> None:
    task = queue.enqueue("clip.mp4")
    for stage in STAGE_ORDER:
        queue.complete_stage(task.id, stage)

    assert queue.get(task.id).next_stage() is None


def test_max_concurrent_is_exposed(db: sqlite3.Connection) -> None:
    assert TaskQueue(db, max_concurrent=7).max_concurrent == 7


def test_has_capacity_reflects_active_work(db: sqlite3.Connection) -> None:
    queue = TaskQueue(db, max_concurrent=1)
    queue.enqueue("a.jpg")

    assert queue.has_capacity() is True
    queue.claim_next()
    assert queue.has_capacity() is False
