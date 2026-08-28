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

import logging
import re
import threading
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

from app.core.config import settings

logger = logging.getLogger("nexus.retrieval")

# Deliberately off-domain sentences used to auto-calibrate the dense relevance
# gate.  At startup we measure how similar the corpus is to these (with whatever
# embedding model is loaded); the gate is set just above that background level so
# it self-calibrates on a model swap instead of relying on a hardcoded threshold.
# These are intentionally generic non-FM text and never need to change with the
# corpus or model.
_OFF_DOMAIN_PROBES = [
    "what is the capital of France",
    "recipe for chocolate chip cookies",
    "best football team of all time",
    "how do I change a car tyre",
    "history of the Roman empire",
    "lyrics to a popular song",
]

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

# Marks a section as carrying the document's identity (vendor/client/site/agreement
# no.) -- in competitor-comparison docs this lives in its own "Parties and Site
# Details" section rather than the preamble.
_IDENTITY_RE = re.compile(
    r"^\|\s*(?:Company|Client|Vendor|Primary Vendor|Facility|Site|Agreement No\.?|Service Category)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Cap each chunk's body. Agent-routed queries can gather up to 4 chunks on top
# of the system prompt + conversation history, so each chunk needs to stay lean
# to keep CPU prefill time bounded -- 1500 chars (~375 tokens) keeps 4 chunks
# plus everything else comfortably under n_ctx=4096 without truncation risk.
_MAX_CHUNK_CHARS = 1500


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
    overlap_chars = settings.retrieval_chunk_overlap_chars
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

        # Build content sections list so we can reference the previous body for overlap.
        content_sections = [
            (level, heading, body)
            for level, heading, body in sections
            if heading != "Header" and body
        ]
        prev_body = ""
        for level, heading, body in content_sections:
            # Prepend the tail of the preceding section so queries matching content
            # at a section boundary appear in both the preceding and the current chunk.
            overlap = ""
            if overlap_chars > 0 and prev_body:
                tail = prev_body.strip()[-overlap_chars:]
                if tail:
                    overlap = f"[…continued from previous section]\n{tail}\n\n"
            text = f"{header}\n\n# {heading}\n{overlap}{body}" if header else f"# {heading}\n{overlap}{body}"
            chunks.append(Chunk(source_doc=rel, section=heading, text=text[:_MAX_CHUNK_CHARS]))
            prev_body = body
    return chunks


def _min_max(arr: np.ndarray) -> np.ndarray:
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def _apply_owner_mask(combined: np.ndarray, owners: list, owner: str | None) -> np.ndarray:
    """Base-corpus chunks (owner None) and admin-uploaded "global" chunks are always
    eligible for every user; any other owner-tagged chunk is only eligible for the
    requesting `owner`. Fast path: if there are no user docs at all, the array is
    returned unchanged, so retrieval with no uploads is byte-identical to before."""
    if not any(o is not None for o in owners):
        return combined
    mask = np.fromiter((o is None or o == "global" or o == owner for o in owners), dtype=bool, count=len(owners))
    out = combined.copy()
    out[~mask] = -1e9
    return out


class Retriever:
    def __init__(self):
        self.chunks = _load_chunks()
        # Owner tag parallel to `chunks`: None = committed base corpus (always
        # searched); a profile id = a user-uploaded doc (searched only for that user).
        self.owners: list[str | None] = [None] * len(self.chunks)
        self._lock = threading.RLock()

        self._bm25 = BM25Okapi([_tokenize(c.text) for c in self.chunks])

        from sentence_transformers import SentenceTransformer

        self._embedder = SentenceTransformer(settings.retrieval_embedding_model)
        embeddings = self._embedder.encode(
            [c.text for c in self.chunks], normalize_embeddings=True, show_progress_bar=False
        )
        self._embeddings = np.asarray(embeddings, dtype=np.float32)

        # Cross-encoder re-ranker: loaded only when enabled so that disabling it
        # via config avoids downloading the ~66 MB model.
        self._reranker = None
        if settings.retrieval_reranker_enabled:
            from sentence_transformers import CrossEncoder
            self._reranker = CrossEncoder(settings.retrieval_reranker_model)

        # Dense relevance-gate threshold, auto-calibrated to this model + corpus.
        self.min_dense_score = self._calibrate_dense_gate()

    def _calibrate_dense_gate(self) -> float:
        """Set the dense gate just above the corpus's similarity to off-domain
        text, so an off-topic query (which scores near that background) is gated
        out while in-domain queries (which score well above it) pass.  Returns the
        fixed configured value when auto-calibration is disabled."""
        if not settings.retrieval_dense_gate_auto or self._embeddings.shape[0] == 0:
            return settings.retrieval_min_dense_score
        background = 0.0
        for probe in _OFF_DOMAIN_PROBES:
            sim = float((self._embeddings @ self._encode_query(probe)).max())
            background = max(background, sim)
        threshold = round(background * settings.retrieval_dense_gate_factor, 4)
        logger.info(
            "dense gate auto-calibrated: off-domain background=%.3f -> min_dense_score=%.3f",
            background, threshold,
        )
        return threshold

    def _encode_query(self, query: str) -> np.ndarray:
        """Encode a query with the optional BGE instruction prefix.

        BGE models are trained with an asymmetric instruction: queries get a short
        prefix that moves their embeddings into "passage retrieval" space, while
        passage/chunk texts are encoded without any prefix.  MiniLM and other
        symmetric models leave the instruction blank and this is a no-op.
        """
        q_text = f"{settings.retrieval_query_instruction}{query}" if settings.retrieval_query_instruction else query
        return self._embedder.encode([q_text], normalize_embeddings=True, show_progress_bar=False)[0]

    def _rerank(self, query: str, candidates: list[dict], k: int) -> list[dict]:
        """Re-order candidates using the cross-encoder and return top-k.

        The cross-encoder attends to both the query and the passage simultaneously,
        giving a much more accurate relevance signal than the bi-encoder cosine
        score.  At 20 candidates and a MiniLM-L6 cross-encoder, this runs in
        roughly 50–150 ms on CPU — negligible compared to generation time.
        """
        if self._reranker is None or len(candidates) <= k:
            return candidates[:k]
        pairs = [(query, c["text"]) for c in candidates]
        scores = self._reranker.predict(pairs, show_progress_bar=False)
        ranked = sorted(zip(scores, candidates), key=lambda x: -x[0])
        return [c for _, c in ranked[:k]]

    def add_documents(self, docs: list[dict]) -> None:
        """Append user-uploaded chunks to the in-memory index (chunks + owners +
        embeddings + BM25). Each doc needs source_doc, section, text, embedding
        (float list), owner. Builds new structures and swaps them under the lock so a
        concurrent retrieve() always sees a consistent chunks/embeddings/BM25 set."""
        if not docs:
            return
        new_chunks = [Chunk(source_doc=d["source_doc"], section=d.get("section") or "", text=d["text"]) for d in docs]
        new_owners = [d.get("owner") for d in docs]
        new_emb = np.asarray([d["embedding"] for d in docs], dtype=np.float32)
        with self._lock:
            chunks = self.chunks + new_chunks
            owners = self.owners + new_owners
            embeddings = np.vstack([self._embeddings, new_emb]) if self._embeddings.size else new_emb
            bm25 = BM25Okapi([_tokenize(c.text) for c in chunks])
            self.chunks, self.owners, self._embeddings, self._bm25 = chunks, owners, embeddings, bm25
        logger.info("retriever: +%d user chunks (total=%d)", len(new_chunks), len(self.chunks))

    def retrieve(self, query: str, k: int | None = None, owner: str | None = None) -> list[dict]:
        """Return up to `k` chunks ranked by a hybrid BM25 + dense score, each with
        `source_doc`, `section`, `text`, `score` (combined, for ranking), `dense_score`
        (raw cosine similarity) and `bm25_score` (raw BM25 score) -- the latter two for
        the relevance gate.

        `owner` scopes user-uploaded docs: the base corpus is always searched; a user
        doc is only searched for its owner (None = base corpus only, the default).

        When the cross-encoder is enabled, `retrieval_reranker_candidates` chunks
        are fetched from the BM25+dense stage and then re-ranked to the final top-k.
        """
        # Consistent snapshot (add_documents swaps these atomically under the lock).
        with self._lock:
            chunks, owners, embeddings, bm25 = self.chunks, self.owners, self._embeddings, self._bm25
        if not chunks:
            return []
        k = k or settings.retrieval_top_k
        # Fetch more candidates than needed when re-ranking is on; the cross-encoder
        # picks the best k from the wider set.
        fetch_k = max(k, settings.retrieval_reranker_candidates) if self._reranker else k

        bm25_scores = np.asarray(bm25.get_scores(_tokenize(query)), dtype=np.float32)
        query_emb = self._encode_query(query)
        dense_scores = embeddings @ query_emb

        w = settings.retrieval_bm25_weight
        combined = w * _min_max(bm25_scores) + (1 - w) * _min_max(dense_scores)
        combined = _apply_owner_mask(combined, owners, owner)

        top_idx = np.argsort(-combined)[:fetch_k]
        candidates = [
            {
                "source_doc": chunks[i].source_doc,
                "section": chunks[i].section,
                "text": chunks[i].text,
                "score": float(combined[i]),
                "dense_score": float(dense_scores[i]),
                "bm25_score": float(bm25_scores[i]),
            }
            for i in top_idx
            if combined[i] > -1e8  # drop owner-masked chunks
        ]
        return self._rerank(query, candidates, k)


@lru_cache(maxsize=1)
def get_embedder():
    """Shared sentence-transformers embedder (bge-small-en), so document ingestion
    reuses the same model instance the retriever loads rather than loading a second."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.retrieval_embedding_model)


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()


# ---------------------------------------------------------------------------
# Entity-Aware (Graph-style) Retriever
# ---------------------------------------------------------------------------

class EntityAwareRetriever(Retriever):
    """Extends the hybrid BM25+dense retriever with entity-anchored retrieval.

    When the query mentions a known entity (vendor name, agreement number,
    site name), chunks from the matched document are retrieved first with a
    high anchor score, before BM25+dense fills any remaining slots from the
    full corpus.

    This prevents competitor-comparison documents from polluting vendor-
    specific queries (e.g. "Summit Lift terms" should not pull chunks from
    the Apex One lift comparison doc just because both mention lift PMVs).

    Comparison vs. conventional Retriever:
    - Conventional: top-k from corpus ranked purely by BM25+dense score
    - Entity-Aware: entity-matched chunks first → BM25+dense for remainder
    """

    def retrieve(self, query: str, k: int | None = None, owner: str | None = None) -> list[dict]:
        from app.core.entity_registry import get_entity_registry

        k = k or settings.retrieval_top_k
        registry = get_entity_registry()
        matched_docs = registry.find_docs(query)

        if not matched_docs:
            # No entity match — fall back to standard retrieval (owner-scoped).
            return super().retrieve(query, k, owner=owner)

        # Consistent snapshot (add_documents swaps these atomically under the lock).
        with self._lock:
            chunks, owners, embeddings, bm25 = self.chunks, self.owners, self._embeddings, self._bm25

        # Separate chunks into: entity-anchored (matched docs) vs. rest
        anchor_doc = matched_docs[0]  # highest-scoring entity match
        anchor_indices = [i for i, c in enumerate(chunks) if c.source_doc == anchor_doc]
        anchor_set0 = set(anchor_indices)
        rest_indices = [i for i in range(len(chunks)) if i not in anchor_set0]

        # Score the full corpus normally
        bm25_scores = np.asarray(bm25.get_scores(_tokenize(query)), dtype=np.float32)
        query_emb = self._encode_query(query)
        dense_scores = embeddings @ query_emb
        w = settings.retrieval_bm25_weight
        combined = w * _min_max(bm25_scores) + (1 - w) * _min_max(dense_scores)
        # Anchors are corpus docs (owner None) — always eligible. Owner-mask the fill
        # pool so another user's uploaded chunks can't leak in.
        combined = _apply_owner_mask(combined, owners, owner)

        # Anchor chunks: take up to ceil(k * 0.67) from the matched document
        anchor_slots = max(1, round(k * 0.67))
        anchor_sorted = sorted(anchor_indices, key=lambda i: -combined[i])
        chosen_anchors = anchor_sorted[:anchor_slots]

        # Fill remaining slots from the rest of the corpus (owner-masked chunks excluded)
        fill_slots = k - len(chosen_anchors)
        chosen_set = set(chosen_anchors)
        fill_sorted = sorted(rest_indices, key=lambda i: -combined[i])
        chosen_fill = [i for i in fill_sorted if i not in chosen_set and combined[i] > -1e8][:fill_slots]

        final_indices = chosen_anchors + chosen_fill
        anchor_set = set(chosen_anchors)

        candidates = [
            {
                "source_doc": chunks[i].source_doc,
                "section": chunks[i].section,
                "text": chunks[i].text,
                "score": float(combined[i]),
                "dense_score": float(dense_scores[i]),
                "bm25_score": float(bm25_scores[i]),
                "entity_anchored": i in anchor_set,
            }
            for i in final_indices
        ]
        # Re-rank the final assembled set.  This reorders within the chosen pool
        # without changing which documents are represented (the anchor allocation
        # already guaranteed the right document coverage).
        return self._rerank(query, candidates, k)


@lru_cache(maxsize=1)
def get_entity_retriever() -> EntityAwareRetriever:
    return EntityAwareRetriever()


def add_user_documents(docs: list[dict]) -> None:
    """Append ingested chunks to BOTH live retriever singletons (standard + entity)."""
    get_retriever().add_documents(docs)
    get_entity_retriever().add_documents(docs)


def rehydrate_user_documents() -> int:
    """At startup, reload persisted user-doc chunks from Supabase into the in-memory
    index so uploads survive Space restarts. Best-effort; returns the count added."""
    from app.core.document_store import get_document_store

    store = get_document_store()
    if store is None:
        return 0
    try:
        rows = store.all_chunks()
    except Exception as exc:  # noqa: BLE001
        logger.warning("doc rehydrate skipped (%s)", exc)
        return 0
    docs = [
        {
            "source_doc": r["source_doc"],
            "section": r.get("section") or "",
            "text": r["text"],
            "embedding": r["embedding"],
            "owner": r.get("owner"),
        }
        for r in rows
        if r.get("embedding") and r.get("text")
    ]
    if docs:
        add_user_documents(docs)
    return len(docs)
