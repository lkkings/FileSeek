"""The model worker process and the handle the service uses to talk to it.

The worker owns the models for one tier. Requests arrive on one queue, responses
leave on another, correlated by request id. Loading is reached through an
importable factory path so the child can build its own models under spawn, where
nothing is inherited from the parent.
"""

from __future__ import annotations

import multiprocessing as mp
import queue as queue_module
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol

from fileseek.models.protocol import (
    DescribeModels,
    EncodeImages,
    EncodeQuery,
    EncodeTextQuery,
    EncodeTexts,
    Failure,
    ModelDescription,
    Ready,
    RecognizeText,
    Request,
    Response,
    Shutdown,
    Text,
    Vectors,
)
from fileseek.models.tiers import ModelSelection, downgrade_to_cpu, select_models

DEFAULT_STARTUP_TIMEOUT = 120.0

DEFAULT_REQUEST_TIMEOUT = 300.0

# Batching earns several times the throughput of per-frame calls, because the
# per-call transfer and launch overhead dominates at batch size 1.
DEFAULT_IMAGE_BATCH_SIZE = {"gpu": 32, "cpu": 8}


class Encoders(Protocol):
    """What the worker needs from a loaded tier."""

    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]: ...

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]: ...

    def encode_query(self, query: str) -> list[float]: ...

    def encode_text_query(self, query: str) -> list[float]: ...

    def recognize_text(self, image: bytes) -> str: ...

    def describe(self) -> tuple[str, str, int, int]: ...


class EncoderFactory(Protocol):
    def __call__(self, selection: ModelSelection) -> Encoders: ...


class OutOfMemoryError(RuntimeError):
    """Raised by a factory when the tier does not fit in memory."""


def load_factory(dotted_path: str) -> EncoderFactory:
    module_name, _, attribute = dotted_path.rpartition(".")
    if not module_name:
        raise ValueError(f"expected a dotted path to a factory, got {dotted_path!r}")
    factory: EncoderFactory = getattr(import_module(module_name), attribute)
    return factory


def _is_out_of_memory(error: BaseException) -> bool:
    if isinstance(error, OutOfMemoryError):
        return True
    text = str(error).lower()
    return "out of memory" in text or "cuda oom" in text


def _load_with_downgrade(
    selection: ModelSelection, factory: EncoderFactory
) -> tuple[Encoders, ModelSelection, tuple[str, ...]]:
    """Load the chosen tier, or fall back to CPU when it will not fit."""
    try:
        return factory(selection), selection, ()
    except Exception as error:
        if not _is_out_of_memory(error):
            raise
        fallback = downgrade_to_cpu(selection, str(error))
        return factory(fallback), fallback, (fallback.reason,)


def _handle(request: Request, encoders: Encoders, active: ModelSelection) -> Response:
    if isinstance(request, EncodeImages):
        vectors = encoders.encode_images(request.images)
        return Vectors(request.request_id, tuple(tuple(vector) for vector in vectors))
    if isinstance(request, EncodeTexts):
        vectors = encoders.encode_texts(request.texts)
        return Vectors(request.request_id, tuple(tuple(vector) for vector in vectors))
    if isinstance(request, EncodeQuery):
        return Vectors(request.request_id, (tuple(encoders.encode_query(request.query)),))
    if isinstance(request, EncodeTextQuery):
        return Vectors(request.request_id, (tuple(encoders.encode_text_query(request.query)),))
    if isinstance(request, RecognizeText):
        return Text(request.request_id, encoders.recognize_text(request.image))
    image_model, text_model, image_dimensions, text_dimensions = encoders.describe()
    return ModelDescription(
        request_id=request.request_id,
        tier=active.tier,
        device=active.device,
        image_model=image_model,
        text_model=text_model,
        image_dimensions=image_dimensions,
        text_dimensions=text_dimensions,
    )


def worker_main(
    requests: mp.Queue[Request],
    responses: mp.Queue[Response],
    selection: ModelSelection,
    factory_path: str,
) -> None:
    """Child entry point: load one tier, then serve requests until shutdown."""
    factory = load_factory(factory_path)
    try:
        encoders, active, notes = _load_with_downgrade(selection, factory)
    except Exception as error:
        responses.put(Failure("startup", "load_failed", str(error)))
        return

    responses.put(Ready(tier=active.tier, device=active.device, notes=notes))

    while True:
        request = requests.get()
        if isinstance(request, Shutdown):
            return
        try:
            response = _handle(request, encoders, active)
        except Exception as error:  # noqa: BLE001 - reported to the parent, not swallowed
            kind = "out_of_memory" if _is_out_of_memory(error) else "encode_failed"
            responses.put(Failure(request.request_id, kind, str(error)))  # type: ignore[arg-type]
            continue

        responses.put(response)


class WorkerFailedError(RuntimeError):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(f"model worker failed ({kind}): {message}")
        self.kind = kind
        self.message = message


class WorkerTimeoutError(TimeoutError):
    def __init__(self, what: str, seconds: float) -> None:
        super().__init__(f"model worker did not {what} within {seconds:.0f}s")


class UnexpectedResponseError(RuntimeError):
    def __init__(self, expected: type[object], received: object) -> None:
        super().__init__(f"expected a {expected.__name__} response, got {type(received).__name__}")


def _expect[ExpectedT: Response](response: Response, expected: type[ExpectedT]) -> ExpectedT:
    """Narrow a response to the shape its request implies.

    A plain assert would vanish under `-O`, leaving a mismatched reply to surface
    as a confusing AttributeError instead of a clear protocol error.
    """
    if not isinstance(response, expected):
        raise UnexpectedResponseError(expected, response)
    return response


@dataclass
class WorkerHandle:
    """Parent-side handle: starts the child and correlates replies by request id."""

    selection: ModelSelection
    factory_path: str
    startup_timeout: float = DEFAULT_STARTUP_TIMEOUT
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT

    def __post_init__(self) -> None:
        # Spawn, not fork: a forked CUDA context is unusable in the child.
        self._context = mp.get_context("spawn")
        self._requests: mp.Queue[Request] | None = None
        self._responses: mp.Queue[Response] | None = None
        self._process: mp.process.BaseProcess | None = None
        self._ready: Ready | None = None

    @property
    def ready(self) -> Ready | None:
        return self._ready

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def start(self) -> Ready:
        requests: mp.Queue[Request] = self._context.Queue()
        responses: mp.Queue[Response] = self._context.Queue()
        process = self._context.Process(
            target=worker_main,
            args=(requests, responses, self.selection, self.factory_path),
            daemon=True,
        )
        process.start()
        self._requests, self._responses, self._process = requests, responses, process

        try:
            first = responses.get(timeout=self.startup_timeout)
        except queue_module.Empty as error:
            self.stop()
            raise WorkerTimeoutError("become ready", self.startup_timeout) from error

        if isinstance(first, Failure):
            self.stop()
            raise WorkerFailedError(first.kind, first.message)

        ready = _expect(first, Ready)
        self._ready = ready
        return ready

    def _exchange(self, request: Request) -> Response:
        if self._requests is None or self._responses is None:
            raise RuntimeError("worker is not running; call start() first")
        self._requests.put(request)
        try:
            response = self._responses.get(timeout=self.request_timeout)
        except queue_module.Empty as error:
            raise WorkerTimeoutError("answer", self.request_timeout) from error
        if isinstance(response, Failure):
            raise WorkerFailedError(response.kind, response.message)
        return response

    def encode_images(
        self, images: Sequence[bytes], request_id: str = "images"
    ) -> list[list[float]]:
        response = _expect(self._exchange(EncodeImages(request_id, tuple(images))), Vectors)
        return [list(vector) for vector in response.vectors]

    def encode_texts(self, texts: Sequence[str], request_id: str = "texts") -> list[list[float]]:
        response = _expect(self._exchange(EncodeTexts(request_id, tuple(texts))), Vectors)
        return [list(vector) for vector in response.vectors]

    def encode_query(self, query: str, request_id: str = "query") -> list[float]:
        response = _expect(self._exchange(EncodeQuery(request_id, query)), Vectors)
        return list(response.vectors[0])

    def encode_text_query(self, query: str, request_id: str = "text-query") -> list[float]:
        response = _expect(self._exchange(EncodeTextQuery(request_id, query)), Vectors)
        return list(response.vectors[0])

    def recognize_text(self, image: bytes, request_id: str = "ocr") -> str:
        response = _expect(self._exchange(RecognizeText(request_id, image)), Text)
        return response.text

    def describe(self, request_id: str = "describe") -> ModelDescription:
        return _expect(self._exchange(DescribeModels(request_id)), ModelDescription)

    def stop(self, timeout: float = 10.0) -> None:
        if self._process is None:
            return
        if self._process.is_alive() and self._requests is not None:
            self._requests.put(Shutdown())
            self._process.join(timeout)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout)
        self._process = None
        self._requests = None
        self._responses = None

    def __enter__(self) -> WorkerHandle:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()


def image_batch_size(selection: ModelSelection | None = None) -> int:
    active = selection if selection is not None else select_models()
    return DEFAULT_IMAGE_BATCH_SIZE[active.tier]
