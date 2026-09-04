import os
import shutil
import hashlib
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from typing import List, Optional

from cognishift.app.db.database import get_db
from cognishift.app.db.models import KnowledgeSourceResponse, DocumentProcessingJobResponse, DocumentPageResponse
from cognishift.app.config import settings
from cognishift.core.retriever import process_pdf, chroma_client, purge_knowledge_source
from cognishift.core.security import resolve_workspace_path
from cognishift.app.core.auth import get_current_user, verify_workspace_access, User
from fastapi import Depends

router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge"])

@router.post("/upload", response_model=KnowledgeSourceResponse)
async def upload_document(
    workspace_id: int = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user)
):
    # 0. Authorization check
    verify_workspace_access(workspace_id, user)

    # 1. Validate file extension (case-insensitive)
    filename = file.filename or "document.pdf"
    ext = Path(filename).suffix.lower()
    if ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
        raise HTTPException(status_code=400, detail="Only PDF (.pdf), PNG (.png), and JPEG (.jpg/.jpeg) files are supported.")

    # 2. Validate workspace existence BEFORE saving to disk
    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM workspaces WHERE id = ?", (workspace_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Workspace not found.")

    # 3. Stream content with early byte-count cutoff (streaming spooler)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    hasher = hashlib.sha256()
    safe_basename = Path(filename).name
    unique_filename = f"{uuid.uuid4().hex[:8]}_{safe_basename}"
    
    # Store directly into canonical workspace-scoped uploads/
    target_rel_path = f"uploads/{unique_filename}"
    file_path = resolve_workspace_path(workspace_id, target_rel_path, purpose="write", allow_create_parent=True)

    bytes_written = 0
    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(65536):
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise HTTPException(
                        status_code=413, 
                        detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb}MB."
                    )
                hasher.update(chunk)
                buffer.write(chunk)
    except HTTPException:
        if file_path.exists():
            file_path.unlink()
        raise

    checksum = hasher.hexdigest()

    # 4. Insert record into database as 'processing'
    source_type = "pdf" if ext == ".pdf" else "image"
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO knowledge_sources 
               (workspace_id, name, source_type, original_filename, local_path, processing_status, checksum) 
               VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING *""",
            (workspace_id, safe_basename, source_type, safe_basename, str(file_path), "processing", checksum)
        )
        row = await cursor.fetchone()
        await db.commit()
        source_id = row["id"]

    # 6. Process document (Native PDF, OCR, or Vision)
    try:
        from cognishift.core.document_processing.service import DocumentProcessingService
        service = DocumentProcessingService()
        proc_result = await service.process_document(
            workspace_id=workspace_id,
            source_id=source_id,
            file_path=file_path,
            filename=safe_basename
        )
        
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM knowledge_sources WHERE id = ?",
                (source_id,)
            )
            updated_row = await cursor.fetchone()
            return KnowledgeSourceResponse.model_validate(dict(updated_row))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")

@router.get("", response_model=List[KnowledgeSourceResponse])
async def list_knowledge_sources(
    workspace_id: int = Query(...),
    user: User = Depends(get_current_user)
):
    """List all knowledge sources for an authorized workspace."""
    verify_workspace_access(workspace_id, user)
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM knowledge_sources WHERE workspace_id = ? ORDER BY created_at DESC", 
            (workspace_id,)
        )
        rows = await cursor.fetchall()
        return [KnowledgeSourceResponse.model_validate(dict(row)) for row in rows]

@router.get("/{source_id}", response_model=KnowledgeSourceResponse)
async def get_knowledge_source(
    source_id: int,
    user: User = Depends(get_current_user)
):
    """Retrieve details for a single knowledge source with workspace authorization check."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM knowledge_sources WHERE id = ?", (source_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Knowledge source not found.")
        verify_workspace_access(row["workspace_id"], user)
        return KnowledgeSourceResponse.model_validate(dict(row))

@router.delete("/{source_id}")
async def delete_knowledge_source(
    source_id: int,
    user: User = Depends(get_current_user)
):
    """Delete a document, its physical file, and its vectors from ChromaDB with authorization check."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM knowledge_sources WHERE id = ?", (source_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Knowledge source not found.")
        
        workspace_id = row["workspace_id"]
        verify_workspace_access(workspace_id, user)

        # 1. Mark status as 'deleting' in SQLite
        await db.execute("UPDATE knowledge_sources SET processing_status = 'deleting' WHERE id = ?", (source_id,))
        await db.commit()

        # 2. Purge vectors from ChromaDB
        try:
            await purge_knowledge_source(workspace_id=workspace_id, source_id=source_id)
        except Exception as e:
            await db.execute("UPDATE knowledge_sources SET processing_status = 'deletion_failed' WHERE id = ?", (source_id,))
            await db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to purge vector embeddings from ChromaDB: {str(e)}. Source marked as deletion_failed."
            )

        # 3. Clean document pages and jobs
        await db.execute("DELETE FROM document_pages WHERE source_id = ?", (source_id,))
        await db.execute("DELETE FROM document_processing_jobs WHERE source_id = ?", (source_id,))

        # 4. Remove physical file from disk
        local_path = row["local_path"]
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass

        # 5. Delete database record
        await db.execute("DELETE FROM knowledge_sources WHERE id = ?", (source_id,))
        await db.commit()

        return {"status": "deleted", "source_id": source_id, "message": "Document and vector embeddings purged."}

@router.get("/{source_id}/jobs", response_model=List[DocumentProcessingJobResponse])
async def list_processing_jobs(
    source_id: int,
    user: User = Depends(get_current_user)
):
    """List all processing jobs and versions for a knowledge source."""
    async with get_db() as db:
        cursor = await db.execute("SELECT workspace_id FROM knowledge_sources WHERE id = ?", (source_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Knowledge source not found.")
        verify_workspace_access(row["workspace_id"], user)

        cursor = await db.execute(
            "SELECT * FROM document_processing_jobs WHERE source_id = ? ORDER BY id DESC",
            (source_id,)
        )
        job_rows = await cursor.fetchall()
        return [DocumentProcessingJobResponse.model_validate(dict(r)) for r in job_rows]


@router.get("/{source_id}/pages", response_model=List[DocumentPageResponse])
async def list_document_pages(
    source_id: int,
    user: User = Depends(get_current_user)
):
    """List all extracted pages and OCR/Vision provenance for a knowledge source."""
    async with get_db() as db:
        cursor = await db.execute("SELECT workspace_id FROM knowledge_sources WHERE id = ?", (source_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Knowledge source not found.")
        verify_workspace_access(row["workspace_id"], user)

        cursor = await db.execute(
            "SELECT * FROM document_pages WHERE source_id = ? ORDER BY page_number ASC",
            (source_id,)
        )
        page_rows = await cursor.fetchall()
        return [DocumentPageResponse.model_validate(dict(r)) for r in page_rows]

