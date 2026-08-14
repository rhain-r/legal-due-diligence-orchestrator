"""Blocks -> chunks, the unit of delegation.

Two rules, both load-bearing:

1. Never split mid-paragraph. A cap on damages severed across a chunk boundary
   reads as absent to both halves.
2. Prefer to break at section boundaries, so a worker assigned "liability" tends
   to receive whole sections rather than fragments.
"""

from __future__ import annotations

from agent.schemas import Chunk, TextBlock


def chunk_blocks(
    blocks: list[TextBlock],
    *,
    target_chars: int = 6000,
    overlap_blocks: int = 1,
) -> list[Chunk]:
    """Group blocks into chunks of roughly `target_chars`.

    `overlap_blocks` repeats the tail of each chunk at the head of the next, so a
    clause that straddles a boundary is fully visible to at least one worker.
    """
    if not blocks:
        return []
    if overlap_blocks < 0:
        raise ValueError("overlap_blocks must be >= 0")

    chunks: list[Chunk] = []
    current: list[TextBlock] = []
    size = 0
    fresh = 0  # blocks added since the last flush, excluding carried-over overlap

    def flush() -> None:
        nonlocal current, size, fresh
        if not current:
            return
        chunks.append(Chunk(chunk_id=f"c{len(chunks):03d}", blocks=list(current)))
        tail = current[-overlap_blocks:] if overlap_blocks else []
        current = list(tail)
        size = sum(len(b.text) for b in current)
        fresh = 0

    for block in blocks:
        block_len = len(block.text)
        starts_new_section = (
            bool(current)
            and block.section_ref is not None
            and block.section_ref != current[-1].section_ref
        )

        # Break early at a section boundary once the chunk is substantial, so
        # chunks align with the document's own structure rather than a byte count.
        too_large = size + block_len > target_chars
        good_seam = starts_new_section and size > target_chars * 0.6
        if current and (too_large or good_seam):
            flush()

        current.append(block)
        size += block_len
        fresh += 1

    # Final flush. Skipped when the remainder is only carried-over overlap, which
    # would otherwise emit a trailing chunk containing nothing new.
    if current and fresh:
        chunks.append(Chunk(chunk_id=f"c{len(chunks):03d}", blocks=list(current)))

    return chunks


def select_chunks_for_terms(chunks: list[Chunk], terms: list[str]) -> list[Chunk]:
    """Chunks whose text mentions any term, preserving document order.

    Used by the orchestrator to scope a worker to relevant chunks. Returns all
    chunks when nothing matches, because "no keyword hit" is emphatically not
    evidence of absence — that judgement belongs to a worker, not a substring test.
    """
    lowered = [t.lower() for t in terms if t.strip()]
    if not lowered:
        return chunks
    hits = [c for c in chunks if any(t in c.text.lower() for t in lowered)]
    return hits or chunks
