"""Entity registry for graph-style entity-aware retrieval.

Builds a bidirectional index of the entities (vendor, site, service category,
agreement number) that identify each corpus document, so vendor/contract queries
can be anchored to the right document before BM25+dense fills the rest.

Phase 3: the entities now come from the self-describing corpus index
(app/core/corpus_index.py), which extracts clean vendor / site / category /
agreement fields per document at ingest. This replaces the previous approach of
re-scanning the raw text with document-format-specific regexes (which mis-parsed
some address formats and only matched full legal names, so natural queries like
"Apex Climate terms" missed). Matching is now token-based with a role tiebreaker
so a query naming a current vendor anchors to that live contract, not a
market-benchmark document that happens to share a word.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from functools import lru_cache

from app.core.corpus_index import get_corpus_index

logger = logging.getLogger("nexus.entity_registry")

# Tokens too generic to identify a specific vendor/site — dropped from the match
# index so a shared legal suffix or category word doesn't anchor unrelated docs.
_STOP_TOKENS = {
    "pvt", "ltd", "llp", "limited", "private", "inc", "corp", "co", "and", "the",
    "services", "systems", "solutions", "technologies", "group", "works",
    "engineers", "mechanical", "facility", "hygiene", "guarding", "risk",
    "management",
}

# Role priority for tie-breaking find_docs results: a named current vendor should
# anchor to its live contract, not a competitor benchmark of the same category.
_ROLE_RANK = {"current": 2, "benchmark": 1, "reference": 0}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _sig_tokens(text: str | None) -> set[str]:
    """Distinctive lowercase tokens from a name (>=3 chars, non-stopword)."""
    return {
        t for t in _TOKEN_RE.findall((text or "").lower())
        if len(t) >= 3 and t not in _STOP_TOKENS
    }


class EntityRegistry:
    """Entity ↔ document index built from the self-describing corpus index."""

    def __init__(self):
        # Public: doc -> readable entity strings (vendor, category, site) — used by
        # tools.list_known_vendors to describe each contract.
        self._doc_to_entities: dict[str, list[str]] = defaultdict(list)
        # Internal match index.
        self._doc_tokens: dict[str, set[str]] = {}
        self._doc_agreement: dict[str, str] = {}
        self._doc_role: dict[str, str] = {}
        self._build()

    def _build(self) -> None:
        ci = get_corpus_index()
        for m in ci._docs.values():
            doc = m.source_doc
            # Readable entities (order matters: vendor, category, site shown first).
            self._doc_to_entities[doc] = [
                v for v in (m.vendor, m.category, m.site, m.agreement_no) if v
            ]
            # Match tokens: vendor + site + category (category lets service-term
            # queries like "fire safety" / "access control" anchor to the vendor).
            self._doc_tokens[doc] = (
                _sig_tokens(m.vendor) | _sig_tokens(m.site) | _sig_tokens(m.category)
            )
            self._doc_role[doc] = m.role
            if m.agreement_no:
                self._doc_agreement[doc] = m.agreement_no.lower()

        logger.info(
            "entity registry: %d documents indexed from corpus index", len(self._doc_to_entities),
        )

    def find_docs(self, query: str) -> list[str]:
        """Return source_doc paths whose entities the query references, best first.

        Scores an exact agreement-number match highly, then counts distinct
        vendor/site/category tokens present in the query. Ties break by role so a
        current contract outranks a benchmark of the same category.
        """
        ql = query.lower()
        score: dict[str, int] = defaultdict(int)

        for doc, agreement in self._doc_agreement.items():
            if agreement in ql:
                score[doc] += 10

        for doc, tokens in self._doc_tokens.items():
            hits = sum(1 for t in tokens if re.search(rf"\b{re.escape(t)}\b", ql))
            if hits:
                score[doc] += hits

        return sorted(
            score,
            key=lambda d: (-score[d], -_ROLE_RANK.get(self._doc_role.get(d, ""), 0)),
        )

    def entities_for_doc(self, source_doc: str) -> list[str]:
        return self._doc_to_entities.get(source_doc, [])


@lru_cache(maxsize=1)
def get_entity_registry() -> EntityRegistry:
    return EntityRegistry()
