"""Document ingestion: parse (with OCR fallback) -> chunk -> batched SLM enrichment
-> embed. Produces chunks ready to persist and to append to the in-memory index.

This module is deliberately decoupled from retrieval and the chat pipeline: it only
returns data. Wiring the chunks into the live index happens elsewhere, so ingestion
can never affect chat response timing.
"""

from __future__ import annotations

import io
import json
import logging
import re

from app.core.config import settings

logger = logging.getLogger("nexus.ingest")

SUPPORTED_EXT = {"pdf", "docx", "txt", "md", "markdown"}


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = reader.pages[: settings.document_max_pages]
    text = "\n\n".join((p.extract_text() or "") for p in pages).strip()
    # Scanned PDF → almost no extractable text → OCR fallback.
    if pages and len(text) / len(pages) < 50:
        try:
            ocr = _ocr_pdf(data)
            if len(ocr) > len(text):
                logger.info("PDF looked scanned — used OCR (%d -> %d chars)", len(text), len(ocr))
                return ocr
        except Exception as exc:  # noqa: BLE001
            logger.warning("OCR failed (%s); using extracted text", exc)
    return text


def _ocr_pdf(data: bytes) -> str:
    import pytesseract
    from pdf2image import convert_from_bytes

    images = convert_from_bytes(data, first_page=1, last_page=settings.document_max_pages)
    return "\n\n".join(pytesseract.image_to_string(img) for img in images).strip()


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()


def extract_text(filename: str, data: bytes) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        return _extract_pdf(data)
    if ext == "docx":
        return _extract_docx(data)
    if ext in ("txt", "md", "markdown"):
        return data.decode("utf-8", errors="ignore").strip()
    raise ValueError(f"Unsupported format: .{ext}")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, source_base: str) -> list[dict]:
    """Paragraph-aware chunks near `document_chunk_chars`, hard-splitting any
    oversized paragraph. Returns dicts with a namespaced source_doc + section."""
    size = settings.document_chunk_chars
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    raw: list[str] = []
    buf = ""
    for p in paras:
        if len(p) > size:
            if buf:
                raw.append(buf)
                buf = ""
            for i in range(0, len(p), size):
                raw.append(p[i : i + size])
        elif len(buf) + len(p) + 2 <= size:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            raw.append(buf)
            buf = p
    if buf:
        raw.append(buf)

    raw = raw[: settings.document_max_chunks]
    return [{"source_doc": f"{source_base}#{i + 1}", "section": f"Part {i + 1}", "text": c} for i, c in enumerate(raw)]


# ---------------------------------------------------------------------------
# SLM steps: doc summary + batched per-chunk enrichment
# ---------------------------------------------------------------------------

_SUMMARY_PROMPT = """\
Summarise this document for a facilities-management knowledge base. Return ONLY JSON:
{{"title": "short title", "summary": "one sentence on what it covers", "category": "e.g. HVAC, Compliance, Vendor, SOP, General"}}

Document (start):
{head}"""

_ENRICH_PROMPT = """\
For each numbered passage below, list 3-6 salient keywords or named entities (systems,
vendors, sites, obligations, figures) that a search should match. Return ONLY JSON:
{{"0": ["kw", ...], "1": [...], ...}} using the passage numbers.

{passages}"""


def _groq(api_key: str, model: str, prompt: str, max_tokens: int):
    from groq import Groq

    client = Groq(api_key=api_key, max_retries=1)
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.0,
    )
    return r.choices[0].message.content or ""


def summarize_doc(text: str, api_key: str | None, model: str, filename: str) -> dict:
    fallback = {"title": filename, "summary": "", "category": "General"}
    if not api_key:
        return fallback
    try:
        raw = _groq(api_key, model, _SUMMARY_PROMPT.format(head=text[:2000]), 150)
        m = re.search(r"\{[\s\S]+\}", raw)
        data = json.loads(m.group()) if m else {}
        return {
            "title": str(data.get("title") or filename)[:200],
            "summary": str(data.get("summary") or "")[:500],
            "category": str(data.get("category") or "General")[:60],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("doc summary failed (%s)", exc)
        return fallback


def enrich_chunks(texts: list[str], api_key: str | None, model: str) -> list[str]:
    """Return a keyword string per chunk. Batched (config batch size) so a big doc
    is a handful of Groq calls, not one-per-chunk — rate-limit safe. Best-effort."""
    if not api_key:
        return [""] * len(texts)
    out = [""] * len(texts)
    batch = max(1, settings.document_enrich_batch)
    for start in range(0, len(texts), batch):
        group = texts[start : start + batch]
        passages = "\n\n".join(f"[{i}] {t[:600]}" for i, t in enumerate(group))
        try:
            raw = _groq(api_key, model, _ENRICH_PROMPT.format(passages=passages), 400)
            m = re.search(r"\{[\s\S]+\}", raw)
            data = json.loads(m.group()) if m else {}
            for i in range(len(group)):
                kws = data.get(str(i)) or []
                if isinstance(kws, list):
                    out[start + i] = ", ".join(str(k) for k in kws[:8])
        except Exception as exc:  # noqa: BLE001
            logger.warning("enrichment batch failed (%s)", exc)
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def ingest_document(filename: str, data: bytes, owner: str, api_key: str | None, model: str) -> dict:
    """Full pipeline for one doc. Returns {meta, chunks} where each chunk has
    source_doc, section, text (clean, for BM25 + context) and embedding (float list,
    computed over text + enrichment keywords so dense recall gets the boost)."""
    text = extract_text(filename, data)
    if not text or len(text) < 20:
        raise ValueError("No extractable text (scanned image with no OCR text, or an empty file).")

    source_base = f"user_docs/{owner}/{filename}"
    chunks = chunk_text(text, source_base)
    meta = summarize_doc(text, api_key, model, filename)
    header = "\n".join(part for part in (meta["title"], meta["summary"]) if part)
    keywords = enrich_chunks([c["text"] for c in chunks], api_key, model)

    from app.core.retrieval import get_embedder

    embed_inputs, stored_texts = [], []
    for c, kw in zip(chunks, keywords):
        clean = f"{header}\n\n{c['text']}" if header else c["text"]
        stored_texts.append(clean[: settings.document_chunk_chars + 400])
        embed_inputs.append(clean + (f"\n\nKeywords: {kw}" if kw else ""))

    embeddings = get_embedder().encode(embed_inputs, normalize_embeddings=True, show_progress_bar=False)
    for c, clean, emb in zip(chunks, stored_texts, embeddings):
        c["text"] = clean
        c["embedding"] = [float(x) for x in emb]

    logger.info("ingested %r for %r: %d chunks (%d chars)", filename, owner, len(chunks), len(text))
    return {"meta": meta, "chunks": chunks}
