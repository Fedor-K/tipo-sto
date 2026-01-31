# -*- coding: utf-8 -*-
"""
Knowledge Base API - REST endpoints for document management and search.
"""
import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.knowledge_base import get_kb_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3
    min_relevance: float = 0.3


# ==================== Documents ====================


@router.get("/documents")
async def list_documents():
    """List all documents in the knowledge base."""
    kb = get_kb_service()
    return {"documents": kb.get_documents()}


@router.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a document (PDF, DOCX, TXT, MD)."""
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 100 MB)")

    # Write to temp file for processing
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        kb = get_kb_service()
        result = await kb.add_document(
            file_path=tmp_path,
            filename=file.filename or "unknown",
            content_type=file.content_type,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Get document details and chunks."""
    kb = get_kb_service()
    doc = kb.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its chunks."""
    kb = get_kb_service()
    deleted = kb.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "document_id": document_id}


# ==================== Search ====================


@router.post("/search")
async def search_knowledge_base(req: SearchRequest):
    """Search the knowledge base with a natural language query."""
    kb = get_kb_service()
    results = await kb.search(
        query=req.query,
        top_k=req.top_k,
        min_relevance=req.min_relevance,
    )
    return {"query": req.query, "results": results, "count": len(results)}


# ==================== Stats ====================


@router.get("/stats")
async def get_stats():
    """Get knowledge base statistics."""
    kb = get_kb_service()
    return kb.get_stats()


# ==================== Admin UI ====================


@router.get("/admin", include_in_schema=False)
async def admin_ui():
    """Serve the knowledge base admin page."""
    admin_page = Path(__file__).parent.parent / "static" / "admin_kb.html"
    if admin_page.exists():
        return FileResponse(admin_page)
    raise HTTPException(status_code=404, detail="Admin UI not found")
