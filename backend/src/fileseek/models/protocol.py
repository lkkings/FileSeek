"""Messages exchanged with the model worker process.

Encoding runs in its own process so one CUDA context is created and reused, and
so switching model tier is a child restart rather than a service restart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class EncodeImages:
    """Encode raw image bytes. Batched: per-item GPU round trips dominate cost."""

    request_id: str
    images: tuple[bytes, ...]


@dataclass(frozen=True)
class EncodeTexts:
    request_id: str
    texts: tuple[str, ...]


@dataclass(frozen=True)
class EncodeQuery:
    """Encode a search query into the image vector space."""

    request_id: str
    query: str


@dataclass(frozen=True)
class EncodeTextQuery:
    """Encode a search query into the document vector space.

    Separate from EncodeQuery because the two spaces come from different models,
    and separate from EncodeTexts because the text encoder treats a query
    differently from a passage.
    """

    request_id: str
    query: str


@dataclass(frozen=True)
class RecognizeText:
    request_id: str
    image: bytes


@dataclass(frozen=True)
class DescribeModels:
    request_id: str


@dataclass(frozen=True)
class Shutdown:
    request_id: str = "shutdown"


Request = (
    EncodeImages
    | EncodeTexts
    | EncodeQuery
    | EncodeTextQuery
    | RecognizeText
    | DescribeModels
    | Shutdown
)


@dataclass(frozen=True)
class Vectors:
    request_id: str
    vectors: tuple[tuple[float, ...], ...]

    @property
    def dimensions(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0


@dataclass(frozen=True)
class Text:
    request_id: str
    text: str


@dataclass(frozen=True)
class ModelDescription:
    request_id: str
    tier: str
    device: str
    image_model: str
    text_model: str
    image_dimensions: int
    text_dimensions: int


@dataclass(frozen=True)
class Failure:
    request_id: str
    kind: Literal["out_of_memory", "load_failed", "encode_failed", "unknown_request"]
    message: str


@dataclass(frozen=True)
class Ready:
    tier: str
    device: str
    notes: tuple[str, ...] = field(default_factory=tuple)


Response = Vectors | Text | ModelDescription | Failure | Ready
