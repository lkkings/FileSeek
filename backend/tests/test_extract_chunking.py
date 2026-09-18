import pytest

from fileseek.extract.chunking import (
    DEFAULT_CHUNK_CHARS,
    MIN_CHUNK_CHARS,
    chunk_text,
    total_coverage,
)


def test_short_text_becomes_one_chunk() -> None:
    chunks = chunk_text("a short document about deep learning")

    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].char_start == 0


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_long_text_is_split_not_truncated() -> None:
    """The whole document must stay searchable, including its later pages."""
    text = "sentence number one. " * 500

    chunks = chunk_text(text, chunk_chars=500, overlap_chars=50)

    assert len(chunks) > 1
    assert chunks[-1].char_end == len(text)


def test_every_character_is_covered() -> None:
    text = "".join(f"paragraph {n} with some content.\n\n" for n in range(80))

    chunks = chunk_text(text, chunk_chars=400, overlap_chars=60)

    assert total_coverage(chunks) == len(text)


def test_ranges_advance_monotonically() -> None:
    text = "some text that will be split into several pieces. " * 40

    chunks = chunk_text(text, chunk_chars=300, overlap_chars=40)

    starts = [chunk.char_start for chunk in chunks]
    assert starts == sorted(starts)
    assert all(chunk.char_end > chunk.char_start for chunk in chunks)


def test_indexes_are_sequential_from_zero() -> None:
    text = "a repeated sentence for chunking. " * 60

    chunks = chunk_text(text, chunk_chars=300, overlap_chars=30)

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_chunk_text_matches_its_recorded_range() -> None:
    """A hit must be traceable back to the passage that matched."""
    text = "first sentence here. second sentence here. third sentence here. " * 20

    chunks = chunk_text(text, chunk_chars=200, overlap_chars=20)

    for chunk in chunks:
        assert chunk.text == text[chunk.char_start : chunk.char_end].strip()


def test_consecutive_chunks_overlap() -> None:
    text = "one two three four five six seven eight nine ten. " * 40

    chunks = chunk_text(text, chunk_chars=300, overlap_chars=80)

    assert chunks[1].char_start < chunks[0].char_end


def test_zero_overlap_is_allowed() -> None:
    text = "some content to split up here. " * 40

    chunks = chunk_text(text, chunk_chars=200, overlap_chars=0)

    assert chunks[1].char_start == chunks[0].char_end


def test_chunks_respect_the_size_limit() -> None:
    text = "a sentence that goes on for a while. " * 60

    chunks = chunk_text(text, chunk_chars=250, overlap_chars=25)

    assert all(chunk.length <= 250 for chunk in chunks)


def test_split_prefers_a_paragraph_boundary() -> None:
    first = "x" * 200
    second = "y" * 200
    chunks = chunk_text(f"{first}\n\n{second}", chunk_chars=260, overlap_chars=0)

    assert chunks[0].text == first


def test_split_prefers_a_sentence_boundary() -> None:
    text = "First sentence is fairly long here. " + ("y" * 150)

    chunks = chunk_text(text, chunk_chars=100, overlap_chars=0)

    assert chunks[0].text.endswith("here.")


def test_chinese_sentence_boundary_is_honoured() -> None:
    text = "这是第一句关于深度学习的说明。" + ("好" * 150)

    chunks = chunk_text(text, chunk_chars=60, overlap_chars=0)

    assert chunks[0].text.endswith("。")


def test_chinese_text_is_chunked_without_loss() -> None:
    text = "深度学习与注意力机制的研究综述。" * 100

    chunks = chunk_text(text, chunk_chars=300, overlap_chars=40)

    assert total_coverage(chunks) == len(text)


def test_text_without_break_points_still_splits() -> None:
    text = "x" * 1000

    chunks = chunk_text(text, chunk_chars=200, overlap_chars=0)

    assert len(chunks) == 5
    assert total_coverage(chunks) == 1000


def test_chunk_size_below_minimum_is_rejected() -> None:
    with pytest.raises(ValueError, match=f"at least {MIN_CHUNK_CHARS}"):
        chunk_text("some text", chunk_chars=MIN_CHUNK_CHARS - 1)


@pytest.mark.parametrize("overlap", [-1, 200, 500])
def test_invalid_overlap_is_rejected(overlap: int) -> None:
    with pytest.raises(ValueError, match="overlap_chars"):
        chunk_text("some text", chunk_chars=200, overlap_chars=overlap)


def test_default_chunk_size_is_used_when_unspecified() -> None:
    text = "y" * (DEFAULT_CHUNK_CHARS * 2)

    chunks = chunk_text(text)

    assert all(chunk.length <= DEFAULT_CHUNK_CHARS for chunk in chunks)


def test_coverage_of_no_chunks_is_zero() -> None:
    assert total_coverage([]) == 0


def test_whitespace_only_tail_does_not_create_a_chunk() -> None:
    text = ("content here. " * 30) + "\n\n\n   "

    chunks = chunk_text(text, chunk_chars=150, overlap_chars=0)

    assert all(chunk.text for chunk in chunks)


def test_a_very_long_document_produces_many_chunks() -> None:
    text = "This paper surveys recent advances in representation learning. " * 500

    chunks = chunk_text(text)

    assert len(chunks) > 20
    assert chunks[-1].char_end == len(text)
