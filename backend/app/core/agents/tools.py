"""Tool implementations for the Vendor Comparison Agent.

Each tool does a *targeted* lookup restricted to one document type
(current_contracts vs competitor_contracts), unlike the conventional/entity
retrievers which rank across the whole corpus and may surface only one type
if it happens to score higher. The agent calls these explicitly to guarantee
both the current vendor's terms and the competitor benchmark are gathered.

Tool results are returned in the same chunk shape used by Retriever.retrieve()
({"source_doc", "section", "text", ...}) so they can be passed straight into
chat_pipeline._build_user_content() without any reshaping.
"""

from __future__ import annotations

from app.core.entity_registry import EntityRegistry
from app.core.retrieval import Retriever, _tokenize, _min_max
import numpy as np


def _rank_chunks_in_docs(
    retriever: Retriever, query: str, doc_filter_prefix: str, candidate_docs: list[str] | None, k: int
) -> list[dict]:
    """Rank only the chunks belonging to `candidate_docs` (or, if None, any doc
    under `doc_filter_prefix`) by BM25+dense relevance to `query`."""
    indices = [
        i for i, c in enumerate(retriever.chunks)
        if c.source_doc.startswith(doc_filter_prefix)
        and (candidate_docs is None or c.source_doc in candidate_docs)
    ]
    if not indices:
        return []

    bm25_scores = np.asarray(retriever._bm25.get_scores(_tokenize(query)), dtype=np.float32)
    query_emb = retriever._embedder.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
    dense_scores = retriever._embeddings @ query_emb
    w = 0.5
    combined = w * _min_max(bm25_scores) + (1 - w) * _min_max(dense_scores)

    ranked = sorted(indices, key=lambda i: -combined[i])[:k]
    return [
        {
            "source_doc": retriever.chunks[i].source_doc,
            "section": retriever.chunks[i].section,
            "text": retriever.chunks[i].text,
            "score": float(combined[i]),
            "dense_score": float(dense_scores[i]),
            "bm25_score": float(bm25_scores[i]),
        }
        for i in ranked
    ]


# Once a document is matched by entity, the ranking query is biased toward these
# terms so the commercially-relevant sections (not Parties/Signatures boilerplate)
# are what gets returned for renewal/comparison decisions.
_COMMERCIAL_BIAS = "commercial terms scope of services pricing fees SLA cost annual"


def find_vendor_contract(
    retriever: Retriever, registry: EntityRegistry, vendor_or_service: str, k: int = 2
) -> list[dict]:
    """Find chunks from the CURRENT contract matching a vendor name or service type."""
    matched_docs = [
        d for d in registry.find_docs(vendor_or_service) if d.startswith("current_contracts/")
    ]
    rank_query = f"{vendor_or_service} {_COMMERCIAL_BIAS}"
    return _rank_chunks_in_docs(
        retriever, rank_query, "current_contracts/", matched_docs or None, k
    )


def find_competitor_benchmark(
    retriever: Retriever, registry: EntityRegistry, service_category: str, k: int = 2
) -> list[dict]:
    """Find chunks from competitor/market COMPARISON documents for a service category."""
    matched_docs = [
        d for d in registry.find_docs(service_category) if d.startswith("competitor_contracts/")
    ]
    rank_query = f"{service_category} {_COMMERCIAL_BIAS}"
    return _rank_chunks_in_docs(
        retriever, rank_query, "competitor_contracts/", matched_docs or None, k
    )


def list_known_vendors(registry: EntityRegistry) -> list[str]:
    """Returns a readable list of 'Vendor — Service' entries for every current
    contract in the corpus, so the agent can disambiguate an ambiguous query."""
    seen: dict[str, list[str]] = {}
    for doc, entities in registry._doc_to_entities.items():
        if not doc.startswith("current_contracts/"):
            continue
        seen[doc] = entities
    # Each doc's entities include vendor name + service category; join them
    return [f"{doc.split('/')[-1].replace('.txt', '')}: {', '.join(ents[:3])}" for doc, ents in seen.items()]
