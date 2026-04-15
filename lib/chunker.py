"""
Recursive text chunker for RAG pipeline.
Splits text on natural boundaries: paragraphs → sentences → words.
"""

import re

DEFAULT_CHUNK_SIZE = 250    # words
DEFAULT_OVERLAP = 50        # words
DEFAULT_MIN_CHUNK = 50      # words


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_OVERLAP,
    min_chunk_size: int = DEFAULT_MIN_CHUNK,
) -> list[str]:
    trimmed = text.strip()
    if not trimmed:
        return []

    word_count = len(trimmed.split())

    # Short content — return as single chunk
    if word_count <= chunk_size:
        return [trimmed]

    # Split into segments on natural boundaries
    segments = _split_recursive(trimmed)

    # Merge segments into chunks with overlap
    return _merge_segments(segments, chunk_size, chunk_overlap, min_chunk_size)


def _split_recursive(text: str) -> list[str]:
    # Try splitting on double newlines (paragraphs)
    paragraphs = [s.strip() for s in re.split(r"\n\s*\n", text) if s.strip()]
    if len(paragraphs) > 1:
        return paragraphs

    # Try splitting on single newlines
    lines = [s.strip() for s in text.split("\n") if s.strip()]
    if len(lines) > 1:
        return lines

    # Try splitting on sentence boundaries
    sentences = re.findall(r"[^.!?]+[.!?]+\s*", text)
    if len(sentences) > 1:
        return [s.strip() for s in sentences if s.strip()]

    # Last resort — return as-is
    return [text]


def _merge_segments(
    segments: list[str],
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_size: int,
) -> list[str]:
    chunks = []
    current_words: list[str] = []

    for segment in segments:
        segment_words = segment.split()

        # If adding this segment exceeds chunk size, finalize current chunk
        if current_words and len(current_words) + len(segment_words) > chunk_size:
            chunks.append(" ".join(current_words))

            # Keep overlap words from the end
            if chunk_overlap > 0:
                current_words = current_words[-chunk_overlap:]
            else:
                current_words = []

        current_words.extend(segment_words)

        # Force-split if a single segment is bigger than chunk size
        while len(current_words) > chunk_size:
            chunks.append(" ".join(current_words[:chunk_size]))
            current_words = current_words[chunk_size - chunk_overlap :]

    # Don't lose the last chunk
    if current_words:
        last_chunk = " ".join(current_words)
        if len(current_words) < min_chunk_size and chunks:
            chunks[-1] += " " + last_chunk
        else:
            chunks.append(last_chunk)

    return chunks
