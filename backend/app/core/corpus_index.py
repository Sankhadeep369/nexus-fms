"""Self-describing corpus layer (Phase 1 dynamic architecture).

A single ingest pass over the corpus that produces *structured* metadata per
document — vendor, site, service category / FM system, agreement number, term,
expiry — and a per-folder *role* (current | benchmark | reference).  Everything
downstream reads this metadata instead of re-scavenging the raw text with its own
regexes or hardcoding corpus facts in code:

  - the pipeline's doc-class labelling (was a frozen folder→label dict),
  - the portfolio agent's "which docs are current contracts" filter (was the
    string match `"current_contracts" in source_doc`),
  - the entity registry (augments its regex index),
  - dynamic prompt injection — the live set of service domains is rendered into
    the system prompt and agent prompts, so adding a category never leaves a
    hardcoded list stale.

Because of this, adding files, renaming/adding a folder, or introducing a new
service category requires *no code change* — the corpus describes itself.

Extraction strategy: LLM-at-ingest (Groq parses each doc → JSON), gated by a
content hash and cached to `corpus_index.json` next to the data.  Re-extraction
only runs when the corpus (or manifest) actually changes, so the committed cache
means zero cost and instant startup in deployment.  A deterministic markdown
fallback keeps the app fully functional offline / without an API key.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("nexus.corpus_index")

# Filenames co-located with the data (ignored by the retriever's *.txt glob).
_MANIFEST_NAME = "corpus_manifest.json"
_INDEX_CACHE_NAME = "corpus_index.json"

# Roles a document class can play. Drives labelling and the "current contract"
# filter without any folder-name string matching in the consumers.
ROLE_CURRENT = "current"
ROLE_BENCHMARK = "benchmark"
ROLE_REFERENCE = "reference"

_DEFAULT_ROLE_LABELS = {
    ROLE_CURRENT: "CURRENT CONTRACT",
    ROLE_BENCHMARK: "MARKET REFERENCE (benchmark only — not a current agreement)",
    ROLE_REFERENCE: "FM REFERENCE DOCUMENT",
}

# ---------------------------------------------------------------------------
# Deterministic fallback parsing (used when Groq is unavailable or per-doc fails)
# ---------------------------------------------------------------------------

_AGREEMENT_RE = re.compile(r"\bNML-[A-Z]{2}-\d{4}-\d{3,}\b")
_TABLE_ROW = lambda keys: re.compile(  # noqa: E731 - small local helper
    rf"^\|\s*(?:{keys})\s*\|([^|]+)\|", re.IGNORECASE | re.MULTILINE
)
_VENDOR_RE = _TABLE_ROW(r"Vendor|Primary Vendor|Company|Service Provider")
_SITE_RE = _TABLE_ROW(r"Facility|Site|Client|Company\s*/\s*Client")
_CATEGORY_RE = _TABLE_ROW(r"Service Category|Category")
_TERM_RE = _TABLE_ROW(r"Term|Contract Term|Duration")
_EXPIRY_RE = _TABLE_ROW(r"Expiry|Expiry Date|End Date|Valid Until|Renewal Date")


def _cell(text: str) -> str | None:
    val = re.sub(r"\s{2,}", " ", text.strip(" |*")).strip()
    return val or None


def _first(rx: re.Pattern, text: str) -> str | None:
    m = rx.search(text)
    return _cell(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DocMeta:
    source_doc: str          # posix relpath, e.g. "current_contracts/01_Apex...txt"
    doc_class: str           # top-level folder, e.g. "current_contracts"
    role: str                # current | benchmark | reference
    vendor: str | None = None
    site: str | None = None
    system: str | None = None      # normalised FM system, e.g. "HVAC", "Fire & Life Safety"
    category: str | None = None    # service category as stated, e.g. "HVAC AMC"
    agreement_no: str | None = None
    term: str | None = None
    expiry_date: str | None = None


class CorpusIndex:
    """Structured, self-describing view of the corpus."""

    def __init__(self, docs: dict[str, DocMeta], class_labels: dict[str, str]):
        self._docs = docs
        self._class_labels = class_labels

    # --- lookups -----------------------------------------------------------
    def meta(self, source_doc: str) -> DocMeta | None:
        return self._docs.get(source_doc)

    def role_of(self, source_doc: str) -> str:
        m = self._docs.get(source_doc)
        return m.role if m else ROLE_REFERENCE

    def is_current(self, source_doc: str) -> bool:
        return self.role_of(source_doc) == ROLE_CURRENT

    def label_of(self, source_doc: str) -> str:
        doc_class = source_doc.split("/")[0]
        if doc_class in self._class_labels:
            return self._class_labels[doc_class]
        return _DEFAULT_ROLE_LABELS.get(self.role_of(source_doc), "REFERENCE DOCUMENT")

    # --- derived sets ------------------------------------------------------
    @property
    def current_docs(self) -> list[DocMeta]:
        return [m for m in self._docs.values() if m.role == ROLE_CURRENT]

    @staticmethod
    def _distinct_systems(metas) -> list[str]:
        seen: dict[str, None] = {}
        for m in metas:
            label = m.system or m.category
            if label:
                seen.setdefault(label.strip(), None)
        return sorted(seen)

    @property
    def categories(self) -> list[str]:
        """Distinct FM systems/categories across the WHOLE corpus, sorted.

        Includes domain/reference topics as well as contracted systems — use
        `contracted_systems` when you specifically want what is under contract.
        """
        return self._distinct_systems(self._docs.values())

    @property
    def contracted_systems(self) -> list[str]:
        """Distinct FM systems that are actually under active contract (role ==
        current), sorted. This is the live list injected into the system prompt's
        "systems currently under contract" statement, so it never carries a stale
        hardcoded domain list and never leaks reference-doc topics."""
        return self._distinct_systems(self.current_docs)

    @property
    def doc_count(self) -> int:
        return len(self._docs)


# ---------------------------------------------------------------------------
# Manifest + role resolution
# ---------------------------------------------------------------------------

def _load_manifest(corpus_dir: Path) -> dict:
    path = corpus_dir / _MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("corpus_manifest.json unreadable (%s) — using heuristics", exc)
        return {}


def _resolve_class(doc_class: str, manifest: dict) -> tuple[str, str]:
    """Return (role, label) for a doc-class folder.

    Manifest entry wins; otherwise infer the role from the folder name so a
    brand-new folder still gets sensible handling with zero config.
    """
    entry = (manifest.get("doc_classes") or {}).get(doc_class)
    if entry:
        role = entry.get("role") or _infer_role(doc_class)
        label = entry.get("label") or _DEFAULT_ROLE_LABELS.get(role, doc_class)
        return role, label
    role = _infer_role(doc_class)
    label = _DEFAULT_ROLE_LABELS.get(role, doc_class.replace("_", " ").title())
    return role, label


def _infer_role(doc_class: str) -> str:
    name = doc_class.lower()
    if "current" in name or "active" in name:
        return ROLE_CURRENT
    if any(k in name for k in ("competitor", "benchmark", "market", "alternative")):
        return ROLE_BENCHMARK
    return ROLE_REFERENCE


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """\
You are an FM document analyst. Read the document below and extract its identity
as JSON. Return ONLY a JSON object, no other text.

DOCUMENT (filename: {rel}):
{text}

Return exactly:
{{
  "vendor": "<vendor / service-provider company name, or null>",
  "site": "<facility or client/site name, or null>",
  "system": "<the FM system this document concerns as a short label, e.g. 'HVAC', \
'Electrical', 'Fire & Life Safety', 'Security & CCTV', 'Access Control', \
'Lifts & Escalators', 'Plumbing', 'Housekeeping', 'Landscaping', or a suitable \
short label if none fit; null only if the document is not about a specific system>",
  "category": "<service category exactly as stated in the document, e.g. 'HVAC AMC', \
'Guarding & CCTV', or null>",
  "agreement_no": "<agreement / contract number if present, else null>",
  "term": "<contract term string if present, else null>",
  "expiry_date": "<contract end / expiry / renewal date if present, else null>"
}}

Use null for any field genuinely absent. Do not invent values."""


def _extract_deterministic(text: str, rel: str) -> dict:
    category = _first(_CATEGORY_RE, text)
    return {
        "vendor": _first(_VENDOR_RE, text),
        "site": _first(_SITE_RE, text),
        "system": category,  # best-effort: as-stated category doubles as system label
        "category": category,
        "agreement_no": (_AGREEMENT_RE.search(text).group() if _AGREEMENT_RE.search(text) else None),
        "term": _first(_TERM_RE, text),
        "expiry_date": _first(_EXPIRY_RE, text),
    }


def _extract_llm(text: str, rel: str, api_key: str, model: str) -> dict | None:
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _EXTRACT_PROMPT.format(rel=rel, text=text[:3500])}],
            max_tokens=350,
            temperature=0.0,
        )
        raw = resp.choices[0].message.content.strip()
        m = re.search(r"\{[\s\S]+\}", raw)
        if not m:
            return None
        data = json.loads(m.group())
        # Normalise empty strings / "null" strings to None.
        return {k: (v if v not in ("", "null", "None", None) else None) for k, v in data.items()}
    except Exception as exc:
        logger.warning("corpus ingest: LLM extraction failed for %s (%s)", rel, exc)
        return None


# ---------------------------------------------------------------------------
# Build + cache
# ---------------------------------------------------------------------------

def _norm_bytes(path: Path) -> bytes:
    """Read a file and normalise line endings so the fingerprint is stable across
    OSes (a Windows CRLF checkout and a Linux LF checkout of the same commit must
    hash identically, otherwise the committed cache would be rejected on deploy
    and trigger a needless full re-ingest on every cold start)."""
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _corpus_fingerprint(corpus_dir: Path) -> str:
    """Hash of all *.txt contents + the manifest, so the cache invalidates when
    the corpus or its labelling changes but is stable across machines/OSes."""
    h = hashlib.sha256()
    for path in sorted(corpus_dir.rglob("*.txt")):
        h.update(path.relative_to(corpus_dir).as_posix().encode())
        h.update(_norm_bytes(path))
    manifest = corpus_dir / _MANIFEST_NAME
    if manifest.exists():
        h.update(_norm_bytes(manifest))
    return h.hexdigest()


def _build(corpus_dir: Path) -> CorpusIndex:
    manifest = _load_manifest(corpus_dir)
    fingerprint = _corpus_fingerprint(corpus_dir)
    cache_path = corpus_dir / _INDEX_CACHE_NAME

    # --- try cache ---------------------------------------------------------
    cached = None
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cached = None
    if cached and cached.get("fingerprint") == fingerprint:
        docs = {d["source_doc"]: DocMeta(**d) for d in cached["docs"]}
        class_labels = cached.get("class_labels", {})
        logger.info("corpus_index: loaded %d docs from cache (fingerprint match)", len(docs))
        return CorpusIndex(docs, class_labels)

    # --- (re)build ---------------------------------------------------------
    use_llm = bool(settings.groq_api_key)
    logger.info(
        "corpus_index: building (fingerprint changed) via %s extraction ...",
        "LLM" if use_llm else "deterministic",
    )
    docs: dict[str, DocMeta] = {}
    class_labels: dict[str, str] = {}

    for path in sorted(corpus_dir.rglob("*.txt")):
        rel = path.relative_to(corpus_dir).as_posix()
        doc_class = rel.split("/")[0]
        role, label = _resolve_class(doc_class, manifest)
        class_labels.setdefault(doc_class, label)

        text = path.read_text(encoding="utf-8", errors="replace")
        fields = None
        if use_llm:
            fields = _extract_llm(text, rel, settings.groq_api_key, settings.groq_model)
        if fields is None:
            fields = _extract_deterministic(text, rel)

        docs[rel] = DocMeta(
            source_doc=rel,
            doc_class=doc_class,
            role=role,
            vendor=fields.get("vendor"),
            site=fields.get("site"),
            system=fields.get("system"),
            category=fields.get("category"),
            agreement_no=fields.get("agreement_no"),
            term=fields.get("term"),
            expiry_date=fields.get("expiry_date"),
        )

    # --- persist cache -----------------------------------------------------
    try:
        cache_path.write_text(
            json.dumps(
                {
                    "fingerprint": fingerprint,
                    "class_labels": class_labels,
                    "docs": [asdict(m) for m in docs.values()],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        logger.info("corpus_index: built %d docs, cached → %s", len(docs), cache_path.name)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("corpus_index: could not write cache (%s)", exc)

    return CorpusIndex(docs, class_labels)


@lru_cache(maxsize=1)
def get_corpus_index() -> CorpusIndex:
    return _build(settings.corpus_dir)
