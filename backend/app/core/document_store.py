"""Supabase persistence for ingested documents + their chunks/embeddings, so user
docs survive HF Space restarts. Embeddings are stored as JSON float arrays (search
stays in-memory; no pgvector needed)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger("nexus.document_store")


class DocumentStore:
    def __init__(self, url: str, key: str):
        from supabase import create_client

        self._c = create_client(url, key)

    def save(self, owner: str, filename: str, meta: dict, chunks: list[dict]) -> dict[str, Any]:
        doc = (
            self._c.table("documents")
            .insert(
                {
                    "owner": owner,
                    "filename": filename,
                    "title": meta.get("title"),
                    "summary": meta.get("summary"),
                    "category": meta.get("category"),
                    "num_chunks": len(chunks),
                    "status": "ready",
                }
            )
            .execute()
            .data[0]
        )
        rows = [
            {
                "document_id": doc["id"],
                "owner": owner,
                "source_doc": c["source_doc"],
                "section": c["section"],
                "text": c["text"],
                "embedding": c["embedding"],
            }
            for c in chunks
        ]
        for i in range(0, len(rows), 100):  # batch to stay under payload limits
            self._c.table("document_chunks").insert(rows[i : i + 100]).execute()
        return doc

    def list_for_owner(self, owner: str) -> list[dict[str, Any]]:
        return (
            self._c.table("documents")
            .select("id,owner,filename,title,summary,category,num_chunks,created_at")
            .eq("owner", owner)
            .order("created_at", desc=True)
            .execute()
            .data
        )

    def delete(self, doc_id: str, owner: str) -> bool:
        res = self._c.table("documents").delete().eq("id", doc_id).eq("owner", owner).execute()
        return len(res.data) > 0

    def all_chunks(self) -> list[dict[str, Any]]:
        """Every stored chunk (owner, source_doc, section, text, embedding) — used at
        startup to rehydrate the in-memory index."""
        return (
            self._c.table("document_chunks")
            .select("owner,source_doc,section,text,embedding")
            .execute()
            .data
        )


@lru_cache(maxsize=1)
def get_document_store() -> DocumentStore | None:
    from app.core.config import settings

    if not settings.supabase_url or not settings.supabase_anon_key:
        logger.warning("Document store not configured (missing SUPABASE_URL/SUPABASE_ANON_KEY)")
        return None
    return DocumentStore(settings.supabase_url, settings.supabase_anon_key)
