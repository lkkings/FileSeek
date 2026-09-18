"""Splits document text into overlapping chunks for embedding.

Text encoders have a fixed input window, so a long document must be split rather
than truncated: the spec requires that later pages stay searchable. Each chunk
keeps its character range, which is what lets a search hit point back at the
passage that matched.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_CHUNK_CHARS = 1000

# Consecutive chunks overlap so a sentence spanning a boundary still embeds
# intact in at least one of them.
DEFAULT_OVERLAP_CHARS = 150

MIN_CHUNK_CHARS = 50

# A boundary is only worth taking if it leaves at least this share of the chunk
# size. Relative rather than absolute: an absolute floor would reject every
# sentence break whenever chunk_chars itself is small.
MIN_BREAK_FRACTION = 0.25

# Prefer to break here, in descending order of how clean the break is.
_BREAK_POINTS = ("\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", "；", "; ", "，", ", ", " ")


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    char_start: int
    char_end: int

    @property
    def length(self) -> int:
        return self.char_end - self.char_start


def _find_break(text: str, start: int, ideal_end: int, hard_end: int) -> int:
    """Pick a break at or before ideal_end, preferring a sentence boundary.

    Searching backwards from the ideal end keeps chunks under the size limit; if
    nothing suitable is found, the hard limit applies and the split lands
    mid-sentence rather than letting a chunk grow unbounded.
    """
    if hard_end >= len(text):
        return len(text)

    smallest_useful = max(1, int((hard_end - start) * MIN_BREAK_FRACTION))
    window = text[start:ideal_end]
    for marker in _BREAK_POINTS:
        position = window.rfind(marker)
        if position > 0 and position + len(marker) >= smallest_useful:
            return start + position + len(marker)
    return ideal_end


def chunk_text(
    text: str,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[TextChunk]:
    """Split text into chunks that together cover all of it.

    Ranges are half-open and, ignoring the deliberate overlap, contiguous: no part
    of the document is dropped.
    """
    if chunk_chars < MIN_CHUNK_CHARS:
        raise ValueError(f"chunk_chars must be at least {MIN_CHUNK_CHARS}, got {chunk_chars}")
    if not 0 <= overlap_chars < chunk_chars:
        raise ValueError(
            f"overlap_chars must be between 0 and {chunk_chars - 1}, got {overlap_chars}"
        )

    stripped = text.strip()
    if not stripped:
        return []

    chunks: list[TextChunk] = []
    position = 0
    index = 0
    length = len(text)

    while position < length:
        ideal_end = min(position + chunk_chars, length)
        end = _find_break(text, position, ideal_end, position + chunk_chars)
        body = text[position:end]

        if body.strip():
            chunks.append(
                TextChunk(index=index, text=body.strip(), char_start=position, char_end=end)
            )
            index += 1

        if end >= length:
            break
        # Step back by the overlap, but always make forward progress.
        position = max(end - overlap_chars, position + 1)

    return chunks


def total_coverage(chunks: list[TextChunk]) -> int:
    """Characters covered by the chunks, counting overlap once."""
    if not chunks:
        return 0
    covered = 0
    reach = chunks[0].char_start
    for chunk in chunks:
        start = max(chunk.char_start, reach)
        if chunk.char_end > start:
            covered += chunk.char_end - start
            reach = chunk.char_end
    return covered
