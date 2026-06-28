"""Hybrid BM25 + dense-embedding retrieval over the extracted document corpus
(`02_extracted_text/`: current contracts, competitor-comparison contracts, and
domain SOPs/reference docs).

Each source `.txt` file is split into one chunk per top-level markdown section
(`#`/`##` headings). The free-text "header" block that precedes the first heading
-- which carries the agreement number, vendor/client names, site, and service
category for contract files -- is prepended to every chunk from that file, so a
chunk about "Commercial Terms" still carries the vendor/site identity that the
query is implicitly asking about.

Retrieval combines two signals:
- BM25 (lexical/keyword overlap) -- good for exact names, numbers, section titles.
- Dense cosine similarity via a small sentence-transformers model -- good for
  paraphrased/semantic queries that don't share vocabulary with the source text.

The dense score also acts as a relevance gate: if nothing in the corpus is even
loosely related to the query (e.g. a generic "write an email" request), no
context block is injected and the model answers from the system prompt alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

from app.core.config import settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

# Marks a section as carrying the document's identity (vendor/client/site/agreement
# no.) -- in competitor-comparison docs this lives in its own "Parties and Site
# Details" section rather than the preamble.
_IDENTITY_RE = re.compile(
    r"^\|\s*(?:Company|Client|Vendor|Primary Vendor|Facility|Site|Agreement No\.?|Service Category)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Cap each chunk's body. With n_ctx=4096 and 3 chunks we can afford 2000 chars each.
_MAX_CHUNK_CHARS = 2000


def _tokenize(text: str) -> list[str]:
    """Unigram + bigram tokenisation for BM25.

    Adding bigrams allows BM25 to match FM phrases like "preventive maintenance",
    "fire safety", and "annual maintenance contract" as units rather than just
    matching the individual words separately.  Bigrams are joined with '_' so they
    are treated as single vocabulary items by BM25Okapi.
    """
    tokens = _TOKEN_RE.findall(text.lower())
    bigrams = [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    return tokens + bigrams


@dataclass
class Chunk:
    source_doc: str  # e.g. "current_contracts/13_PrimeEdge_Electrical_HQ.txt"
    section: str  # e.g. "5. Commercial Terms"
    text: str  # header block + section content, truncated for context-window safety


def _split_sections(raw: str) -> list[tuple[int, str, str]]:
    """Split a document into (heading_level, heading, body) triples on markdown
    headings (#, ##, ###). Any text before the first heading is returned as level 0
    under the synthetic "Header" key."""
    matches = list(_HEADING_RE.finditer(raw))
    if not matches:
        return [(0, "Document", raw.strip())]

    sections = []
    preamble = raw[: matches[0].start()].strip()
    if preamble:
        sections.append((0, "Header", preamble))

    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        level = len(m.group(1))
        sections.append((level, m.group(2).strip(), raw[start:end].strip()))
    return sections


def _load_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    root = settings.corpus_dir
    for path in sorted(root.rglob("*.txt")):
        raw = path.read_text(encoding="utf-8")
        rel = path.relative_to(root).as_posix()
        sections = _split_sections(raw)

        preamble = next((body for level, heading, body in sections if heading == "Header"), "")

        # A lone top-level (#) heading alongside ##/### subsections is the document's
        # title (e.g. "HVAC Preventive Maintenance and Optimization Agreement") --
        # otherwise it wouldn't be carried into chunks for the other sections.
        top_level_headings = [heading for level, heading, _ in sections if level == 1]
        has_subsections = any(level > 1 for level, _, _ in sections)
        title = top_level_headings[0] if len(top_level_headings) == 1 and has_subsections else ""

        # The first section carrying a "Vendor / Client / Site / ..." identity table --
        # for competitor-comparison docs this lives in its own "Parties and Site
        # Details" section rather than the preamble.
        identity = next(
            (body for level, heading, body in sections if heading != "Header" and _IDENTITY_RE.search(body)), ""
        )

        header = "\n\n".join(part for part in (preamble, title, identity) if part)

        for level, heading, body in sections:
            if heading == "Header" or not body:
                continue
            text = f"{header}\n\n# {heading}\n{body}" if header else f"# {heading}\n{body}"
            chunks.append(Chunk(source_doc=rel, section=heading, text=text[:_MAX_CHUNK_CHARS]))
    return chunks


def _min_max(arr: np.ndarray) -> np.ndarray:
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


class Retriever:
    def __init__(self):
        self.chunks = _load_chunks()

        self._bm25 = BM25Okapi([_tokenize(c.text) for c in self.chunks])

        from sentence_transformers import SentenceTransformer

        self._embedder = SentenceTransformer(settings.retrieval_embedding_model)
        embeddings = self._embedder.encode(
            [c.text for c in self.chunks], normalize_embeddings=True, show_progress_bar=False
        )
        self._embeddings = np.asarray(embeddings, dtype=np.float32)

    def retrieve(self, query: str, k: int | None = None) -> list[dict]:
        """Return up to `k` chunks ranked by a hybrid BM25 + dense score, each with
        `source_doc`, `section`, `text`, `score` (combined, for ranking), `dense_score`
        (raw cosine similarity) and `bm25_score` (raw BM25 score) -- the latter two for
        the relevance gate."""
        if not self.chunks:
            return []
        k = k or settings.retrieval_top_k

        bm25_scores = np.asarray(self._bm25.get_scores(_tokenize(query)), dtype=np.float32)
        query_emb = self._embedder.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
        dense_scores = self._embeddings @ query_emb

        w = settings.retrieval_bm25_weight
        combined = w * _min_max(bm25_scores) + (1 - w) * _min_max(dense_scores)

        top_idx = np.argsort(-combined)[:k]
        return [
            {
                "source_doc": self.chunks[i].source_doc,
                "section": self.chunks[i].section,
                "text": self.chunks[i].text,
                "score": float(combined[i]),
                "dense_score": float(dense_scores[i]),
                "bm25_score": float(bm25_scores[i]),
            }
            for i in top_idx
        ]


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()
