"""Entity registry for Graph-style entity-aware retrieval.

Scans the corpus at startup and builds a bidirectional index:
  entity_name → [source_doc paths]
  source_doc  → [entity names]

Entity types extracted:
  - Vendors (from Vendor/Primary Vendor rows in document headers)
  - Sites / Facilities (from Facility/Site rows)
  - Agreement numbers (NML-FS-YYYY-NNN pattern)
  - Service categories (Lifts, HVAC, CCTV, etc.)

Used by EntityAwareRetriever to anchor vendor/contract queries to the
correct source documents before BM25+dense fills the remaining slots.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("nexus.entity_registry")

# Patterns for extracting entities from document text
_AGREEMENT_RE = re.compile(r"\bNML-[A-Z]{2}-\d{4}-\d{3,}\b")
_VENDOR_ROW_RE = re.compile(
    r"^\|\s*(?:Vendor|Primary Vendor|Company|Service Provider)\s*\|([^|]+)\|",
    re.IGNORECASE | re.MULTILINE,
)
_SITE_ROW_RE = re.compile(
    r"^\|\s*(?:Facility|Site|Client|Company\s*/\s*Client)\s*\|([^|]+)\|",
    re.IGNORECASE | re.MULTILINE,
)
_SERVICE_ROW_RE = re.compile(
    r"^\|\s*(?:Service Category|Category)\s*\|([^|]+)\|",
    re.IGNORECASE | re.MULTILINE,
)


def _clean(text: str) -> str:
    """Strip markdown, addresses, and extra whitespace from a table cell."""
    # Remove anything that looks like an address (numbers + road/street/floor)
    text = re.sub(r"\d+\w*\s+(?:Floor|Metro|MG|Avenue|Road|Street|Plaza|Layout|HSR)[^|]*", "", text, flags=re.IGNORECASE)
    # Remove postal codes, country names
    text = re.sub(r"\b(?:India|USA|UK|560\d{3}|7\d{4})\b", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text.strip(" |")).strip()


def _extract_entities(text: str) -> list[str]:
    entities: list[str] = []

    for m in _AGREEMENT_RE.finditer(text):
        entities.append(m.group().lower())

    for pattern in (_VENDOR_ROW_RE, _SITE_ROW_RE, _SERVICE_ROW_RE):
        for m in pattern.finditer(text):
            name = _clean(m.group(1))
            if name and len(name) > 3:
                entities.append(name.lower())

    return list(dict.fromkeys(entities))  # deduplicate, preserve order


class EntityRegistry:
    """Bidirectional entity ↔ document index built from the corpus."""

    def __init__(self, corpus_dir: Path):
        self._entity_to_docs: dict[str, list[str]] = defaultdict(list)
        self._doc_to_entities: dict[str, list[str]] = defaultdict(list)
        self._build(corpus_dir)

    def _build(self, corpus_dir: Path) -> None:
        count = 0
        for path in sorted(corpus_dir.rglob("*.txt")):
            text = path.read_text(encoding="utf-8", errors="replace")
            rel = path.relative_to(corpus_dir).as_posix()
            entities = _extract_entities(text)
            for ent in entities:
                self._entity_to_docs[ent].append(rel)
                self._doc_to_entities[rel].append(ent)
            if entities:
                count += 1

        logger.info(
            "entity registry: %d documents indexed, %d unique entities",
            count,
            len(self._entity_to_docs),
        )

    def find_docs(self, query: str) -> list[str]:
        """Return source_doc paths whose entities appear in the query.
        Ordered by number of entity matches (most specific first)."""
        query_lower = query.lower()
        score: dict[str, int] = defaultdict(int)
        for entity, docs in self._entity_to_docs.items():
            if entity in query_lower:
                for doc in docs:
                    score[doc] += 1
        return sorted(score, key=lambda d: -score[d])

    def entities_for_doc(self, source_doc: str) -> list[str]:
        return self._doc_to_entities.get(source_doc, [])


@lru_cache(maxsize=1)
def get_entity_registry() -> EntityRegistry:
    return EntityRegistry(settings.corpus_dir)
