import os
import json
import hashlib
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from typing import List, Optional

from cognishift.app.db.database import get_db
from cognishift.app.db.models import KnowledgeSourceResponse, DocumentProcessingJobResponse, DocumentPageResponse
from cognishift.app.config import settings
from cognishift.core.retriever import purge_knowledge_source
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
    if ext in [".xls", ".doc"]:
        raise HTTPException(
            status_code=400,
            detail="Legacy .doc/.xls format is unsupported. Please convert your file to modern .docx/.xlsx or .pdf format."
        )
    if ext not in [".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".csv", ".docx"]:
        raise HTTPException(
            status_code=400,
            detail="Supported formats: PDF (.pdf), Word (.docx), Excel (.xlsx), CSV (.csv), PNG (.png), and JPEG (.jpg/.jpeg)."
        )

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
    source_type = "docx" if ext == ".docx" else ("spreadsheet" if ext in [".xlsx", ".xls", ".csv"] else ("pdf" if ext == ".pdf" else "image"))
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

    # 5. Process document
    if ext in [".xlsx", ".csv"]:
        # Spreadsheet Ingestion: Parse sheets, create structured markdown tables, embed and index
        try:
            import openpyxl
            import csv
            import asyncio
            from openpyxl.utils import get_column_letter
            from cognishift.core.retriever import chroma_client, embedding_model
            from cognishift.core.document_insights import detect_header_row_index

            chunks = []
            metadatas = []
            ids = []
            MAX_WINDOW_CHARS = 3500

            def _process_sheet_rows(sheet_name: str, raw_rows: list, sheet_idx: int):
                if not raw_rows:
                    return
                header_idx = detect_header_row_index(raw_rows)
                raw_header = raw_rows[header_idx]
                headers = [str(c).strip() if c is not None and str(c).strip() else f"Col_{i+1}" for i, c in enumerate(raw_header)]
                header_row_num = header_idx + 1
                data_rows = raw_rows[header_idx + 1:]
                total_cols = max(1, len(headers))
                default_col_start = get_column_letter(1)
                default_col_end = get_column_letter(total_cols)

                header_prefix = f"=== SPREADSHEET: {safe_basename} | SHEET: {sheet_name} (Header Row: #{header_row_num}) ===\nColumns: {', '.join(headers)}\n"

                current_lines = []
                current_chars = len(header_prefix)
                chunk_start_row = None
                chunk_end_row = None

                for r_idx, row in enumerate(data_rows):
                    orig_row = header_row_num + 1 + r_idx
                    if not any(c is not None and str(c).strip() for c in row):
                        continue

                    row_str = f"Row #{orig_row}: " + " | ".join(str(c).strip() if c is not None else "" for c in row)
                    row_chars = len(row_str) + 1

                    # If an individual row exceeds the budget, subsegment it without dropping
                    if row_chars > MAX_WINDOW_CHARS - 500:
                        if current_lines:
                            chunk_text = header_prefix + "\n".join(current_lines)
                            chunks.append(chunk_text)
                            meta = {
                                "source_id": int(source_id),
                                "filename": safe_basename,
                                "document_name": safe_basename,
                                "sheet_name": sheet_name,
                                "header_row": header_row_num,
                                "row_start": chunk_start_row,
                                "row_end": chunk_end_row,
                                "segment_index": 1,
                                "segment_count": 1,
                                "checksum": checksum,
                                "workspace_id": int(workspace_id),
                                "extraction_method": "spreadsheet" if ext == ".xlsx" else "csv",
                                "processing_version": "v1"
                            }
                            if ext == ".xlsx":
                                meta["col_start"] = default_col_start
                                meta["col_end"] = default_col_end
                            metadatas.append(meta)
                            ids.append(f"src_{source_id}_sheet_{sheet_idx + 1}_rows_{chunk_start_row}_{chunk_end_row}_seg_1")
                            current_lines = []
                            current_chars = len(header_prefix)
                            chunk_start_row = None
                            chunk_end_row = None

                        cols_per_slice = 10
                        row_cols = len(row)
                        slices = [row[i:i+cols_per_slice] for i in range(0, row_cols, cols_per_slice)]
                        num_segs = max(1, len(slices))
                        for seg_idx, sl in enumerate(slices, start=1):
                            sl_headers = headers[(seg_idx-1)*cols_per_slice : seg_idx*cols_per_slice]
                            seg_text = (
                                f"=== SPREADSHEET: {safe_basename} | SHEET: {sheet_name} (Row #{orig_row} Segment {seg_idx}/{num_segs}) ===\n"
                                f"Columns: {', '.join(sl_headers)}\n"
                                f"Values: {' | '.join(str(c).strip() if c is not None else '' for c in sl)}"
                            )
                            chunks.append(seg_text)
                            c_start_idx = (seg_idx - 1) * cols_per_slice + 1
                            c_end_idx = min(total_cols, seg_idx * cols_per_slice)
                            meta = {
                                "source_id": int(source_id),
                                "filename": safe_basename,
                                "document_name": safe_basename,
                                "sheet_name": sheet_name,
                                "header_row": header_row_num,
                                "row_start": orig_row,
                                "row_end": orig_row,
                                "segment_index": seg_idx,
                                "segment_count": num_segs,
                                "checksum": checksum,
                                "workspace_id": int(workspace_id),
                                "extraction_method": "spreadsheet" if ext == ".xlsx" else "csv",
                                "processing_version": "v1"
                            }
                            if ext == ".xlsx":
                                meta["col_start"] = get_column_letter(c_start_idx)
                                meta["col_end"] = get_column_letter(c_end_idx)
                            metadatas.append(meta)
                            ids.append(f"src_{source_id}_sheet_{sheet_idx + 1}_rows_{orig_row}_{orig_row}_seg_{seg_idx}")
                        continue

                    # Regular row accumulation
                    if current_chars + row_chars > MAX_WINDOW_CHARS and current_lines:
                        chunk_text = header_prefix + "\n".join(current_lines)
                        chunks.append(chunk_text)
                        meta = {
                            "source_id": int(source_id),
                            "filename": safe_basename,
                            "document_name": safe_basename,
                            "sheet_name": sheet_name,
                            "header_row": header_row_num,
                            "row_start": chunk_start_row,
                            "row_end": chunk_end_row,
                            "segment_index": 1,
                            "segment_count": 1,
                            "checksum": checksum,
                            "workspace_id": int(workspace_id),
                            "extraction_method": "spreadsheet" if ext == ".xlsx" else "csv",
                            "processing_version": "v1"
                        }
                        if ext == ".xlsx":
                            meta["col_start"] = default_col_start
                            meta["col_end"] = default_col_end
                        metadatas.append(meta)
                        ids.append(f"src_{source_id}_sheet_{sheet_idx + 1}_rows_{chunk_start_row}_{chunk_end_row}_seg_1")

                        current_lines = [row_str]
                        current_chars = len(header_prefix) + row_chars
                        chunk_start_row = orig_row
                        chunk_end_row = orig_row
                    else:
                        if not current_lines:
                            chunk_start_row = orig_row
                        current_lines.append(row_str)
                        current_chars += row_chars
                        chunk_end_row = orig_row

                if current_lines:
                    chunk_text = header_prefix + "\n".join(current_lines)
                    chunks.append(chunk_text)
                    meta = {
                        "source_id": int(source_id),
                        "filename": safe_basename,
                        "document_name": safe_basename,
                        "sheet_name": sheet_name,
                        "header_row": header_row_num,
                        "row_start": chunk_start_row,
                        "row_end": chunk_end_row,
                        "segment_index": 1,
                        "segment_count": 1,
                        "checksum": checksum,
                        "workspace_id": int(workspace_id),
                        "extraction_method": "spreadsheet" if ext == ".xlsx" else "csv",
                        "processing_version": "v1"
                    }
                    if ext == ".xlsx":
                        meta["col_start"] = default_col_start
                        meta["col_end"] = default_col_end
                    metadatas.append(meta)
                    ids.append(f"src_{source_id}_sheet_{sheet_idx + 1}_rows_{chunk_start_row}_{chunk_end_row}_seg_1")

            def _parse_spreadsheet():
                if ext == ".xlsx":
                    wb = openpyxl.load_workbook(file_path, data_only=True)
                    for sheet_idx, sname in enumerate(wb.sheetnames):
                        ws = wb[sname]
                        raw_rows = list(ws.iter_rows(values_only=True))
                        _process_sheet_rows(sname, raw_rows, sheet_idx)
                else:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        raw_rows = list(csv.reader(f))
                    _process_sheet_rows("CSV_Data", raw_rows, 0)

            await asyncio.to_thread(_parse_spreadsheet)

            def _embed_and_upsert():
                if chunks:
                    gen = embedding_model.embed(chunks)
                    embs = [e.tolist() if hasattr(e, "tolist") else [float(x) for x in e] for e in gen]
                    col = chroma_client.get_or_create_collection(f"workspace_{workspace_id}")
                    col.upsert(documents=chunks, embeddings=embs, metadatas=metadatas, ids=ids)

            await asyncio.to_thread(_embed_and_upsert)

            # Optional visual tile indexing for XLSX
            if ext == ".xlsx":
                try:
                    from cognishift.core.visual_rag.embedding_provider import get_visual_embedding_provider
                    from cognishift.core.visual_rag.vector_store import get_visual_vector_store
                    from cognishift.core.visual_rag.schemas import PageVectorMetadata
                    from cognishift.core.document_processing.office_renderer import extract_xlsx_structured_content

                    v_prov = get_visual_embedding_provider(allow_simulation=False)
                    if v_prov:
                        _, tiles = await asyncio.to_thread(extract_xlsx_structured_content, file_path)
                        v_store = get_visual_vector_store()
                        for tile_bytes, tile_meta in tiles:
                            p_num = tile_meta.get("page", 1)
                            chk = hashlib.sha256(tile_bytes).hexdigest()
                            vecs = await asyncio.to_thread(v_prov.embed_page, tile_bytes)
                            v_meta = PageVectorMetadata(
                                workspace_id=workspace_id,
                                source_id=source_id,
                                processing_version="v1",
                                page_number=p_num,
                                filename=safe_basename,
                                checksum=chk,
                                image_width=1100,
                                image_height=750,
                                is_diagram_likely=False,
                                contains_tables_likely=True,
                                token_count=len(vecs) if hasattr(vecs, "__len__") else 128
                            )
                            await v_store.upsert_page_vectors(v_meta, vecs)
                    else:
                        logger.warning(f"Visual embedding provider unavailable for {safe_basename}; skipping XLSX visual indexing (allow_simulation=False)")
                except Exception as ve:
                    logger.warning(f"Optional XLSX visual indexing skipped: {ve}")

            async with get_db() as db:
                # Save page/sheet records in document_pages table for direct page retrieval
                for idx, chunk_text in enumerate(chunks, start=1):
                    await db.execute(
                        """INSERT INTO document_pages (source_id, workspace_id, processing_version, page_number, text_content, extraction_method)
                           VALUES (?, ?, 'v1', ?, ?, 'spreadsheet')""",
                        (source_id, workspace_id, idx, chunk_text)
                    )
                await db.execute(
                    "UPDATE knowledge_sources SET processing_status = 'completed', chunk_count = ?, active_processing_version = 'v1' WHERE id = ?",
                    (len(chunks), source_id)
                )
                # Auto-append source_id to agents in this workspace so newly ingested knowledge is immediately accessible
                c_agents = await db.execute("SELECT id, knowledge_source_ids FROM agent_definitions WHERE workspace_id = ?", (workspace_id,))
                for ag in await c_agents.fetchall():
                    try:
                        curr_ids = json.loads(ag["knowledge_source_ids"]) if ag["knowledge_source_ids"] else []
                        if not isinstance(curr_ids, list):
                            curr_ids = []
                    except Exception:
                        curr_ids = []
                    if source_id not in curr_ids:
                        curr_ids.append(source_id)
                        await db.execute(
                            "UPDATE agent_definitions SET knowledge_source_ids = ? WHERE id = ?",
                            (json.dumps(curr_ids), ag["id"])
                        )
                await db.commit()
                cursor = await db.execute("SELECT * FROM knowledge_sources WHERE id = ?", (source_id,))
                updated_row = await cursor.fetchone()
                return KnowledgeSourceResponse.model_validate(dict(updated_row))
        except Exception as e:
            logger.error(f"Failed to process spreadsheet {source_id}: {e}", exc_info=True)
            async with get_db() as db:
                await db.execute("UPDATE knowledge_sources SET processing_status = 'failed' WHERE id = ?", (source_id,))
                await db.commit()
            raise HTTPException(status_code=500, detail="Failed to process spreadsheet. Internal processing error.")

    elif ext == ".docx":
        # DOCX Ingestion: Extract structured sections, headings, and tables
        try:
            from cognishift.core.retriever import chroma_client, embedding_model
            from cognishift.core.document_processing.office_renderer import extract_docx_structured_content

            docx_chunks_data = await asyncio.to_thread(extract_docx_structured_content, file_path)
            chunks = []
            metadatas = []
            ids = []

            for idx, item in enumerate(docx_chunks_data, start=1):
                chunk_text = item["text"]
                chunks.append(chunk_text)
                metadatas.append({
                    "source_id": int(source_id),
                    "filename": safe_basename,
                    "document_name": safe_basename,
                    "section_heading": item.get("section_heading", "General"),
                    "page": int(item.get("page", idx)),
                    "checksum": checksum,
                    "workspace_id": int(workspace_id),
                    "extraction_method": "document",
                    "processing_version": "v1"
                })
                ids.append(f"src_{source_id}_docx_chunk_{idx}")

            if chunks:
                def _embed_and_upsert_docx():
                    gen = embedding_model.embed(chunks)
                    embs = [e.tolist() if hasattr(e, "tolist") else [float(x) for x in e] for e in gen]
                    col = chroma_client.get_or_create_collection(f"workspace_{workspace_id}")
                    col.upsert(documents=chunks, embeddings=embs, metadatas=metadatas, ids=ids)

                await asyncio.to_thread(_embed_and_upsert_docx)

            async with get_db() as db:
                for idx, c_text in enumerate(chunks, start=1):
                    await db.execute(
                        """INSERT INTO document_pages (source_id, workspace_id, processing_version, page_number, text_content, extraction_method)
                           VALUES (?, ?, 'v1', ?, ?, 'document')""",
                        (source_id, workspace_id, idx, c_text)
                    )
                await db.execute(
                    "UPDATE knowledge_sources SET processing_status = 'completed', chunk_count = ?, active_processing_version = 'v1' WHERE id = ?",
                    (len(chunks), source_id)
                )
                c_agents = await db.execute("SELECT id, knowledge_source_ids FROM agent_definitions WHERE workspace_id = ?", (workspace_id,))
                for ag in await c_agents.fetchall():
                    try:
                        curr_ids = json.loads(ag["knowledge_source_ids"]) if ag["knowledge_source_ids"] else []
                        if not isinstance(curr_ids, list):
                            curr_ids = []
                    except Exception:
                        curr_ids = []
                    if source_id not in curr_ids:
                        curr_ids.append(source_id)
                        await db.execute(
                            "UPDATE agent_definitions SET knowledge_source_ids = ? WHERE id = ?",
                            (json.dumps(curr_ids), ag["id"])
                        )
                await db.commit()
                cursor = await db.execute("SELECT * FROM knowledge_sources WHERE id = ?", (source_id,))
                updated_row = await cursor.fetchone()
                return KnowledgeSourceResponse.model_validate(dict(updated_row))
        except Exception as e:
            logger.error(f"Failed to process DOCX {source_id}: {e}", exc_info=True)
            async with get_db() as db:
                await db.execute("UPDATE knowledge_sources SET processing_status = 'failed' WHERE id = ?", (source_id,))
                await db.commit()
            raise HTTPException(status_code=500, detail="Failed to process DOCX document. Internal processing error.")

    # 6. Native PDF, OCR, or Vision
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
            # Auto-append source_id to agents in this workspace so newly ingested knowledge is immediately accessible
            c_agents = await db.execute("SELECT id, knowledge_source_ids FROM agent_definitions WHERE workspace_id = ?", (workspace_id,))
            for ag in await c_agents.fetchall():
                try:
                    curr_ids = json.loads(ag["knowledge_source_ids"]) if ag["knowledge_source_ids"] else []
                    if not isinstance(curr_ids, list):
                        curr_ids = []
                except Exception:
                    curr_ids = []
                if source_id not in curr_ids:
                    curr_ids.append(source_id)
                    await db.execute(
                        "UPDATE agent_definitions SET knowledge_source_ids = ? WHERE id = ?",
                        (json.dumps(curr_ids), ag["id"])
                    )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM knowledge_sources WHERE id = ?",
                (source_id,)
            )
            updated_row = await cursor.fetchone()
            return KnowledgeSourceResponse.model_validate(dict(updated_row))
    except Exception as e:
        logger.error(f"Failed to process document {source_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process document. Internal processing error.")

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

        # 5. Clean agent_definitions knowledge_source_ids
        c_agents = await db.execute("SELECT id, knowledge_source_ids FROM agent_definitions WHERE workspace_id = ?", (workspace_id,))
        for ag in await c_agents.fetchall():
            try:
                curr_ids = json.loads(ag["knowledge_source_ids"]) if ag["knowledge_source_ids"] else []
                if isinstance(curr_ids, list) and source_id in curr_ids:
                    curr_ids.remove(source_id)
                    await db.execute(
                        "UPDATE agent_definitions SET knowledge_source_ids = ? WHERE id = ?",
                        (json.dumps(curr_ids), ag["id"])
                    )
            except Exception:
                pass

        # 6. Delete database record
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

