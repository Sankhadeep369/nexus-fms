"""Shared helpers for the deterministic agents (budget / portfolio / timeline).

These agents compute their answers from the corpus index, not from retrieval, so
they only need the retriever to attach source provenance (which chunk each figure
lives in) for citation and the eval harness.
"""

from __future__ import annotations


def provenance_chunks(retriever, source_docs: set[str]) -> list[dict]:
    """First indexed chunk per contributing document, for source attribution /
    G-Eval. The facts come from the index; this is just where they live."""
    chunks: list[dict] = []
    seen: set[str] = set()
    if retriever is not None and hasattr(retriever, "chunks"):
        for c in retriever.chunks:
            if c.source_doc in source_docs and c.source_doc not in seen:
                seen.add(c.source_doc)
                chunks.append({"source_doc": c.source_doc, "section": c.section, "text": c.text})
    return chunks
