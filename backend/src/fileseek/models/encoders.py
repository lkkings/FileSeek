"""The real encoders, loaded inside the model worker process.

This module is imported by the worker child, never by the service directly: it
pulls in torch and the model weights, which must stay out of the parent process.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fileseek.models.tiers import ModelSelection
from fileseek.models.vectors import normalize
from fileseek.models.weights import WeightStore

# multilingual-e5 is trained asymmetrically: a search string and an indexed
# passage must carry different prefixes or retrieval quality drops noticeably.
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "

# RapidOCR reports each line as (box, text, confidence); below this the "text" is
# usually texture or compression noise rather than words.
MIN_OCR_CONFIDENCE = 0.5


class WeightsMissingError(RuntimeError):
    def __init__(self, repo_id: str, expected_at: Path) -> None:
        super().__init__(f"weights for {repo_id} are not present at {expected_at}")
        self.repo_id = repo_id
        self.expected_at = expected_at


def _resolve(store: WeightStore, repo_id: str) -> Path:
    path = store.path_for(repo_id)
    if not path.is_dir():
        raise WeightsMissingError(repo_id, path)
    return path


class LocalEncoders:
    """Chinese-CLIP for pixels, multilingual-e5 for prose, RapidOCR for text in images."""

    def __init__(self, selection: ModelSelection, store: WeightStore) -> None:
        import torch
        from sentence_transformers import SentenceTransformer
        from transformers import ChineseCLIPModel, ChineseCLIPProcessor

        self._selection = selection
        self._torch = torch
        bundle = selection.bundle

        image_path = _resolve(store, bundle.image.repo_id)
        text_path = _resolve(store, bundle.text.repo_id)

        device = "cuda" if selection.device == "cuda" else selection.device
        self._device = device

        # transformers does not fully type eval()/to(), so the handle is held as
        # Any to keep that gap at this one boundary.
        clip: Any = ChineseCLIPModel.from_pretrained(str(image_path))
        clip.eval()
        if device != "cpu":
            clip = clip.to(device)
        self._clip = clip
        self._clip_processor = ChineseCLIPProcessor.from_pretrained(str(image_path))

        self._text_model = SentenceTransformer(str(text_path), device=device)

        self._ocr: Any | None = None
        self._image_dimensions = bundle.image_dimensions
        self._text_dimensions = bundle.text_dimensions

    @property
    def _reader(self) -> Any:
        """Load the OCR reader on first use; many libraries never need it."""
        if self._ocr is None:
            from rapidocr_onnxruntime import RapidOCR

            self._ocr = RapidOCR()
        return self._ocr

    def _decode(self, payload: bytes) -> Any:
        from PIL import Image

        with Image.open(io.BytesIO(payload)) as image:
            return image.convert("RGB")

    def encode_images(self, images: Sequence[bytes]) -> list[list[float]]:
        if not images:
            return []
        decoded = [self._decode(payload) for payload in images]
        inputs = self._clip_processor(images=decoded, return_tensors="pt")
        if self._device != "cpu":
            inputs = {key: value.to(self._device) for key, value in inputs.items()}

        with self._torch.no_grad():
            features = self._clip.get_image_features(**inputs).pooler_output
        return [normalize([float(value) for value in row]) for row in features.cpu()]

    def encode_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode indexed passages, which take the passage prefix."""
        if not texts:
            return []
        prefixed = [f"{PASSAGE_PREFIX}{text}" for text in texts]
        vectors = self._text_model.encode(prefixed, normalize_embeddings=True)
        return [[float(value) for value in row] for row in vectors]

    def encode_query(self, query: str) -> list[float]:
        """Encode a search string into the image vector space."""
        inputs = self._clip_processor(text=[query], padding=True, return_tensors="pt")
        if self._device != "cpu":
            inputs = {key: value.to(self._device) for key, value in inputs.items()}

        with self._torch.no_grad():
            features = self._clip.get_text_features(**inputs).pooler_output
        return normalize([float(value) for value in features.cpu()[0]])

    def encode_text_query(self, query: str) -> list[float]:
        """Encode a search string into the document vector space."""
        vector = self._text_model.encode([f"{QUERY_PREFIX}{query}"], normalize_embeddings=True)[0]
        return [float(value) for value in vector]

    def recognize_text(self, image: bytes) -> str:
        import numpy as np

        decoded = self._decode(image)
        result, _ = self._reader(np.array(decoded))
        if not result:
            return ""
        lines = [
            str(line[1]) for line in result if len(line) < 3 or float(line[2]) >= MIN_OCR_CONFIDENCE
        ]
        return "\n".join(lines)

    def describe(self) -> tuple[str, str, int, int]:
        bundle = self._selection.bundle
        return (
            bundle.image.repo_id,
            bundle.text.repo_id,
            self._image_dimensions,
            self._text_dimensions,
        )


def make_encoders(selection: ModelSelection) -> LocalEncoders:
    """Factory the worker resolves by dotted path.

    Reads the weight location from settings, so a library kept off the system
    drive is honoured inside the child process too.
    """
    from fileseek.config import load_settings
    from fileseek.paths import AppPaths

    paths = AppPaths.resolve()
    settings = load_settings(paths.config_file)
    resolved = settings.apply_to(paths)
    return LocalEncoders(selection, WeightStore(resolved.model_dir))
