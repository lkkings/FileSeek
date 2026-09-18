import multiprocessing as mp
from collections.abc import Iterator

import pytest

from fileseek.models.hardware import HardwareProfile
from fileseek.models.protocol import (
    DescribeModels,
    EncodeImages,
    Failure,
    ModelDescription,
    Ready,
    Shutdown,
    Vectors,
)
from fileseek.models.tiers import select_models
from fileseek.models.worker import (
    DEFAULT_IMAGE_BATCH_SIZE,
    UnexpectedResponseError,
    WorkerFailedError,
    WorkerHandle,
    WorkerTimeoutError,
    image_batch_size,
    load_factory,
)

FACTORY = "fake_encoders.make_echo"

BIG_GPU = HardwareProfile(has_cuda=True, vram_bytes=12 * 1024**3, device_name="RTX 4070")
CPU_ONLY = HardwareProfile()


@pytest.fixture
def cpu_worker() -> Iterator[WorkerHandle]:
    handle = WorkerHandle(
        selection=select_models(profile=CPU_ONLY),
        factory_path=FACTORY,
        startup_timeout=60.0,
        request_timeout=60.0,
    )
    handle.start()
    yield handle
    handle.stop()


def test_worker_starts_and_reports_ready(cpu_worker: WorkerHandle) -> None:
    assert cpu_worker.is_running is True
    assert cpu_worker.ready is not None
    assert cpu_worker.ready.tier == "cpu"
    assert cpu_worker.ready.device == "cpu"


def test_encode_round_trip_through_the_child_process(cpu_worker: WorkerHandle) -> None:
    vectors = cpu_worker.encode_images([b"abc", b"defgh"])

    assert vectors == [[3.0, 1.0, 0.0, 0.0], [5.0, 1.0, 0.0, 0.0]]


def test_batch_encode_matches_individual_calls(cpu_worker: WorkerHandle) -> None:
    batched = cpu_worker.encode_images([b"a", b"bb", b"ccc"])
    individually = [cpu_worker.encode_images([payload])[0] for payload in (b"a", b"bb", b"ccc")]

    assert batched == individually


def test_encode_texts_round_trip(cpu_worker: WorkerHandle) -> None:
    assert cpu_worker.encode_texts(["ab", "cde"]) == [[2.0, 0.0, 1.0], [3.0, 0.0, 1.0]]


def test_encode_query_returns_a_single_vector(cpu_worker: WorkerHandle) -> None:
    assert cpu_worker.encode_query("猫") == [1.0, 0.0, 0.0, 1.0]


def test_document_queries_use_the_text_space(cpu_worker: WorkerHandle) -> None:
    """Image and document queries target different models, so they are separate calls."""
    visual = cpu_worker.encode_query("猫")
    textual = cpu_worker.encode_text_query("猫")

    assert len(visual) != len(textual)
    assert textual == [1.0, 1.0, 0.0]


def test_recognize_text_round_trip(cpu_worker: WorkerHandle) -> None:
    assert cpu_worker.recognize_text(b"1234") == "ocr:4"


def test_describe_reports_the_active_tier_and_models(cpu_worker: WorkerHandle) -> None:
    description = cpu_worker.describe()

    assert description.tier == "cpu"
    assert description.device == "cpu"
    assert "chinese-clip" in description.image_model
    assert description.image_dimensions == 4
    assert description.text_dimensions == 3


def test_empty_batch_returns_no_vectors(cpu_worker: WorkerHandle) -> None:
    assert cpu_worker.encode_images([]) == []


def test_worker_survives_many_sequential_requests(cpu_worker: WorkerHandle) -> None:
    for index in range(25):
        assert cpu_worker.encode_images([b"x" * (index + 1)])[0][0] == float(index + 1)

    assert cpu_worker.is_running is True


def test_stop_ends_the_child_process(cpu_worker: WorkerHandle) -> None:
    cpu_worker.stop()

    assert cpu_worker.is_running is False


def test_stop_is_idempotent(cpu_worker: WorkerHandle) -> None:
    cpu_worker.stop()
    cpu_worker.stop()

    assert cpu_worker.is_running is False


def test_context_manager_starts_and_stops() -> None:
    handle = WorkerHandle(
        selection=select_models(profile=CPU_ONLY), factory_path=FACTORY, startup_timeout=60.0
    )

    with handle as worker:
        assert worker.is_running is True
        assert worker.encode_texts(["hi"]) == [[2.0, 0.0, 1.0]]

    assert handle.is_running is False


def test_requests_before_start_are_rejected() -> None:
    handle = WorkerHandle(selection=select_models(profile=CPU_ONLY), factory_path=FACTORY)

    with pytest.raises(RuntimeError, match="not running"):
        handle.encode_texts(["hi"])


def test_gpu_tier_that_will_not_fit_downgrades_to_cpu() -> None:
    """An OOM at load time must degrade the tier, not fail the worker."""
    handle = WorkerHandle(
        selection=select_models(profile=BIG_GPU),
        factory_path="fake_encoders.make_oom_on_gpu_load",
        startup_timeout=60.0,
        request_timeout=60.0,
    )

    try:
        ready = handle.start()

        assert ready.tier == "cpu"
        assert ready.device == "cpu"
        assert any("out of memory" in note for note in ready.notes)
        assert handle.encode_texts(["ok"]) == [[2.0, 0.0, 1.0]]
    finally:
        handle.stop()


def test_downgraded_worker_reports_the_cpu_tier_in_describe() -> None:
    handle = WorkerHandle(
        selection=select_models(profile=BIG_GPU),
        factory_path="fake_encoders.make_oom_on_gpu_load",
        startup_timeout=60.0,
        request_timeout=60.0,
    )

    try:
        handle.start()

        assert handle.describe().tier == "cpu"
    finally:
        handle.stop()


def test_load_failure_is_reported_to_the_parent() -> None:
    handle = WorkerHandle(
        selection=select_models(profile=CPU_ONLY),
        factory_path="fake_encoders.make_broken_load",
        startup_timeout=60.0,
    )

    with pytest.raises(WorkerFailedError, match="corrupt") as excinfo:
        handle.start()

    assert excinfo.value.kind == "load_failed"
    assert handle.is_running is False


def test_encode_failure_is_reported_without_killing_the_worker() -> None:
    handle = WorkerHandle(
        selection=select_models(profile=CPU_ONLY),
        factory_path="fake_encoders.make_exploding",
        startup_timeout=60.0,
        request_timeout=60.0,
    )

    try:
        handle.start()

        with pytest.raises(WorkerFailedError, match="could not decode frame") as excinfo:
            handle.encode_images([b"bad"])

        assert excinfo.value.kind == "encode_failed"
        # The worker stays up, so one bad file does not stop the queue.
        assert handle.encode_texts(["still alive"]) == [[11.0, 0.0, 1.0]]
    finally:
        handle.stop()


def test_out_of_memory_during_encode_is_classified() -> None:
    handle = WorkerHandle(
        selection=select_models(profile=CPU_ONLY),
        factory_path="fake_encoders.make_oom_on_encode",
        startup_timeout=60.0,
        request_timeout=60.0,
    )

    try:
        handle.start()

        with pytest.raises(WorkerFailedError) as excinfo:
            handle.encode_images([b"big"])

        assert excinfo.value.kind == "out_of_memory"
    finally:
        handle.stop()


def test_slow_startup_times_out() -> None:
    handle = WorkerHandle(
        selection=select_models(profile=CPU_ONLY),
        factory_path="fake_encoders.make_slow_load",
        startup_timeout=1.0,
    )

    with pytest.raises(WorkerTimeoutError, match="become ready"):
        handle.start()

    assert handle.is_running is False


def test_request_timeout_is_reported(cpu_worker: WorkerHandle) -> None:
    cpu_worker.request_timeout = 0.5
    cpu_worker._responses = mp.get_context("spawn").Queue()  # nothing will arrive

    with pytest.raises(WorkerTimeoutError, match="answer"):
        cpu_worker.encode_texts(["hi"])


def test_mismatched_response_shape_is_reported(cpu_worker: WorkerHandle) -> None:
    """A reply of the wrong shape must surface as a protocol error, not AttributeError."""
    from fileseek.models.protocol import Text

    with pytest.raises(UnexpectedResponseError, match="expected a Vectors response"):
        cpu_worker._exchange = lambda request: Text("r", "not vectors")  # type: ignore[method-assign]
        cpu_worker.encode_texts(["hi"])


def test_load_factory_resolves_a_dotted_path() -> None:
    factory = load_factory(FACTORY)

    assert callable(factory)


def test_load_factory_rejects_a_bare_name() -> None:
    with pytest.raises(ValueError, match="dotted path"):
        load_factory("make_echo")


def test_load_factory_reports_a_missing_attribute() -> None:
    with pytest.raises(AttributeError):
        load_factory("fake_encoders.no_such_factory")


def test_batch_size_is_larger_on_gpu() -> None:
    gpu = image_batch_size(select_models(profile=BIG_GPU))
    cpu = image_batch_size(select_models(profile=CPU_ONLY))

    assert gpu == DEFAULT_IMAGE_BATCH_SIZE["gpu"]
    assert cpu == DEFAULT_IMAGE_BATCH_SIZE["cpu"]
    assert gpu > cpu


def test_batch_size_defaults_to_detected_hardware() -> None:
    assert image_batch_size() in DEFAULT_IMAGE_BATCH_SIZE.values()


def test_protocol_messages_carry_their_request_id() -> None:
    assert EncodeImages("r1", (b"x",)).request_id == "r1"
    assert DescribeModels("r2").request_id == "r2"
    assert Shutdown().request_id == "shutdown"


def test_vectors_reports_its_dimensions() -> None:
    assert Vectors("r", ((1.0, 2.0, 3.0),)).dimensions == 3
    assert Vectors("r", ()).dimensions == 0


def test_ready_defaults_to_no_notes() -> None:
    assert Ready(tier="cpu", device="cpu").notes == ()


def test_failure_and_description_are_plain_records() -> None:
    failure = Failure("r", "load_failed", "boom")
    description = ModelDescription("r", "cpu", "cpu", "img", "txt", 512, 384)

    assert failure.kind == "load_failed"
    assert description.image_dimensions == 512
