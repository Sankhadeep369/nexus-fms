from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.document_store import get_document_store
from app.core.ingest import SUPPORTED_EXT, ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


def _require_store():
    store = get_document_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Document ingestion is not configured (missing Supabase credentials).")
    return store


def _norm_owner(owner: str | None) -> str:
    return (owner or "global").strip().lower() or "global"


@router.post("")
async def upload_document(file: UploadFile = File(...), owner: str = Form("global")):
    """Ingest one document: parse (OCR if scanned) -> chunk -> SLM enrich -> embed ->
    persist. The heavy work runs in a threadpool so it never blocks the event loop or
    live chat streaming."""
    store = _require_store()
    filename = file.filename or "document"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in SUPPORTED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported format .{ext}. Allowed: PDF, DOCX, TXT, MD.")

    data = await file.read()
    if len(data) > settings.document_max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large (max {settings.document_max_mb} MB).")

    owner = _norm_owner(owner)
    try:
        result = await run_in_threadpool(
            ingest_document, filename, data, owner, settings.groq_api_key, settings.groq_model
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(exc)[:160]}")

    doc = await run_in_threadpool(store.save, owner, filename, result["meta"], result["chunks"])

    # Phase 2 will also append result["chunks"] to the live retriever here.
    return {
        "id": doc["id"],
        "filename": filename,
        "title": result["meta"]["title"],
        "summary": result["meta"]["summary"],
        "category": result["meta"]["category"],
        "num_chunks": len(result["chunks"]),
    }


@router.get("")
def list_documents(owner: str = "global"):
    store = _require_store()
    return store.list_for_owner(_norm_owner(owner))


@router.delete("/{doc_id}")
def delete_document(doc_id: str, owner: str = "global"):
    store = _require_store()
    if not store.delete(doc_id, _norm_owner(owner)):
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": True}
