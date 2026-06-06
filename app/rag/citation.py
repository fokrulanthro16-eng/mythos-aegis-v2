"""Citation label generation and formatting.

Citations are derived from filename + chunk_index and are safe to return in
API responses.  Raw embeddings are never included.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.rag.schemas import Citation


def make_citation_label(filename: str, chunk_index: int) -> str:
    """Return a stable, URL-safe citation label.

    Example: ``policy.md`` + chunk 3 → ``policy#chunk-3``
    """
    stem = Path(filename).stem
    safe = re.sub(r"[^\w\-]", "_", stem)
    return f"{safe}#chunk-{chunk_index}"


def build_citations(
    chunks_with_filenames: list[tuple[object, str]],
) -> list[Citation]:
    """Build Citation objects from (DocumentChunk, filename) pairs.

    The caller passes raw ORM objects; this function only reads safe fields.
    """
    from app.db.models.document_chunk import DocumentChunk  # local import avoids cycle

    citations: list[Citation] = []
    for obj, filename in chunks_with_filenames:
        if not isinstance(obj, DocumentChunk):
            continue
        citations.append(
            Citation(
                document_id=obj.document_id,
                filename=filename,
                chunk_index=obj.chunk_index,
                citation_label=obj.citation_label,
            )
        )
    return citations
