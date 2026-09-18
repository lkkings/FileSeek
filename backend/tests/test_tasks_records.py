import pytest

from fileseek.tasks.records import (
    PRIORITY_BATCH,
    PRIORITY_INTERACTIVE,
    STAGE_ORDER,
    IllegalTransitionError,
    Stage,
    TaskRecord,
    TaskStatus,
    can_transition,
    ensure_transition,
)


def make_task(
    status: TaskStatus = "queued",
    *,
    completed_stages: tuple[Stage, ...] = (),
    priority: int = PRIORITY_BATCH,
) -> TaskRecord:
    return TaskRecord(
        id="t1",
        source_path="D:/downloads/clip.mp4",
        status=status,
        created_at=1_700_000_000,
        completed_stages=completed_stages,
        priority=priority,
    )


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        ("queued", "processing"),
        ("queued", "failed"),
        ("processing", "completed"),
        ("processing", "failed"),
        ("processing", "queued"),
        ("failed", "queued"),
    ],
)
def test_legal_transitions_are_allowed(current: TaskStatus, requested: TaskStatus) -> None:
    assert can_transition(current, requested) is True
    ensure_transition(current, requested)


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        ("queued", "completed"),
        ("completed", "processing"),
        ("completed", "queued"),
        ("completed", "failed"),
        ("failed", "completed"),
        ("failed", "processing"),
        ("processing", "processing"),
    ],
)
def test_illegal_transitions_are_rejected(current: TaskStatus, requested: TaskStatus) -> None:
    assert can_transition(current, requested) is False

    with pytest.raises(IllegalTransitionError) as excinfo:
        ensure_transition(current, requested)

    assert excinfo.value.current == current
    assert excinfo.value.requested == requested


def test_completed_is_terminal() -> None:
    for status in ("queued", "processing", "failed", "completed"):
        assert can_transition("completed", status) is False  # type: ignore[arg-type]


def test_interactive_priority_is_recognised() -> None:
    assert make_task(priority=PRIORITY_INTERACTIVE).is_interactive is True
    assert make_task(priority=PRIORITY_BATCH).is_interactive is False


def test_has_completed_reports_recorded_stages() -> None:
    task = make_task(completed_stages=("moved", "extracted"))

    assert task.has_completed("moved") is True
    assert task.has_completed("encoded") is False


def test_next_stage_is_the_first_outstanding_one() -> None:
    assert make_task().next_stage() == "moved"
    assert make_task(completed_stages=("moved",)).next_stage() == "extracted"
    assert make_task(completed_stages=("moved", "extracted")).next_stage() == "encoded"


def test_next_stage_is_none_when_all_done() -> None:
    assert make_task(completed_stages=STAGE_ORDER).next_stage() is None


def test_stage_order_matches_the_pipeline() -> None:
    assert STAGE_ORDER == ("moved", "extracted", "encoded", "indexed")


def test_task_defaults_are_conservative() -> None:
    task = make_task()

    assert task.progress == 0
    assert task.completed_stages == ()
    assert task.error_message is None
    assert task.file_id is None
