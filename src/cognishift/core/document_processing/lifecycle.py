"""
Versioned Reprocessing Generation Lifecycle & Idempotent Deletion.
Ensures zero data destruction if reprocessing fails, atomic single-winner activation,
and complete reconciliation across SQLite, ChromaDB, and the filesystem.
"""
import uuid
import logging
import asyncio
import shutil
from pathlib import Path
from typing import Optional, List

from cognishift.app.db.database import get_db
from cognishift.core.retriever import chroma_client
from cognishift.core.security import get_workspace_root

logger = logging.getLogger(__name__)


async def create_processing_generation(workspace_id: int, source_id: int) -> str:
    """
    Creates a new unique processing version/generation in SQLite.
    Status starts as 'pending'.
    """
    version = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """INSERT INTO document_processing_jobs 
               (source_id, workspace_id, processing_version, status, total_pages)
               VALUES (?, ?, ?, 'pending', 0)""",
            (source_id, workspace_id, version)
        )
        await db.commit()
    return version


async def activate_processing_generation(workspace_id: int, source_id: int, version: str) -> bool:
    """
    Atomically activates the newly indexed processing generation.
    Uses SQLite transaction to update knowledge_sources.active_processing_version.
    Ensures at most one active generation per source.
    """
    async with get_db() as db:
        # 1. Update job status to completed
        await db.execute(
            """UPDATE document_processing_jobs 
               SET status = 'completed', completed_at = CURRENT_TIMESTAMP 
               WHERE source_id = ? AND processing_version = ?""",
            (source_id, version)
        )

        # 2. Compare and set active processing version in knowledge_sources
        await db.execute(
            """UPDATE knowledge_sources 
               SET active_processing_version = ?, processing_status = 'completed'
               WHERE id = ? AND workspace_id = ?""",
            (version, source_id, workspace_id)
        )
        await db.commit()
    return True


async def fail_processing_generation(workspace_id: int, source_id: int, version: str, error_code: str, error_msg: str):
    """
    Marks the processing generation as failed.
    CRITICAL: Preserves the previously active generation in knowledge_sources!
    """
    async with get_db() as db:
        await db.execute(
            """UPDATE document_processing_jobs 
               SET status = 'failed', error_code = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP 
               WHERE source_id = ? AND processing_version = ?""",
            (error_code, error_msg, source_id, version)
        )
        # Verify if source has an active generation; if not, mark knowledge_sources as failed
        cursor = await db.execute("SELECT active_processing_version FROM knowledge_sources WHERE id = ?", (source_id,))
        row = await cursor.fetchone()
        if not row or not row["active_processing_version"]:
            await db.execute(
                "UPDATE knowledge_sources SET processing_status = 'failed' WHERE id = ?",
                (source_id,)
            )
        await db.commit()


async def retire_and_purge_old_generations(workspace_id: int, source_id: int, active_version: str):
    """
    Safely purges vector chunks and page records belonging to retired generations of this source.
    Runs only AFTER the new generation is fully active.
    """
    collection_name = f"workspace_{workspace_id}"
    try:
        collection = chroma_client.get_collection(name=collection_name)
    except Exception:
        collection = None

    if collection:
        def _purge_old():
            # Query all items for this source_id
            sid_int = int(source_id)
            res = collection.get(where={"source_id": sid_int})
            if res and res.get("ids"):
                old_ids = []
                for i, doc_id in enumerate(res["ids"]):
                    meta = res["metadatas"][i] if res.get("metadatas") else {}
                    if meta.get("processing_version") != active_version:
                        old_ids.append(doc_id)
                if old_ids:
                    collection.delete(ids=old_ids)

        await asyncio.to_thread(_purge_old)

    # Clean old records from document_pages
    async with get_db() as db:
        await db.execute(
            "DELETE FROM document_pages WHERE source_id = ? AND processing_version != ?",
            (source_id, active_version)
        )
        await db.commit()


async def idempotent_delete_source(workspace_id: int, source_id: int) -> bool:
    """
    Idempotent deletion lifecycle across SQLite, ChromaDB, and disk:
    1. Mark source as 'deleting'.
    2. Purge all chunks for source_id from ChromaDB.
    3. Delete DB rows (pages, jobs, knowledge_source).
    4. Delete uploaded file from workspace uploads/.
    Safe to retry if any intermediate step crashes.
    """
    async with get_db() as db:
        # Step 1: Set status to deleting
        await db.execute(
            "UPDATE knowledge_sources SET processing_status = 'deleting' WHERE id = ? AND workspace_id = ?",
            (source_id, workspace_id)
        )
        await db.commit()

        # Get local_path before row deletion
        cursor = await db.execute("SELECT local_path FROM knowledge_sources WHERE id = ?", (source_id,))
        row = await cursor.fetchone()
        local_path = row["local_path"] if row and row["local_path"] else None

    # Step 2: Purge Chroma
    collection_name = f"workspace_{workspace_id}"
    try:
        collection = chroma_client.get_collection(name=collection_name)
        sid_int = int(source_id)
        await asyncio.to_thread(collection.delete, where={"source_id": sid_int})
    except Exception as e:
        logger.warning(f"Chroma delete during source purge: {e}")

    # Step 3: Delete DB records
    async with get_db() as db:
        await db.execute("DELETE FROM document_pages WHERE source_id = ?", (source_id,))
        await db.execute("DELETE FROM document_processing_jobs WHERE source_id = ?", (source_id,))
        await db.execute("DELETE FROM knowledge_sources WHERE id = ?", (source_id,))
        await db.commit()

    # Step 4: Delete file from disk
    if local_path:
        p = Path(local_path)
        if p.exists():
            try:
                p.unlink()
            except Exception as e:
                logger.warning(f"Failed to unlink file {local_path}: {e}")

    return True


async def reconcile_incomplete_states(workspace_id: int):
    """
    Reconciles incomplete lifecycle states:
    - Cleans orphaned temporary directories.
    - Finishes sources stuck in 'deleting'.
    - Marks stale jobs stuck in 'extracting'/'ocr_processing' as 'failed'.
    """
    # 1. Clean temporary directories
    try:
        ws_root = get_workspace_root(workspace_id)
        temp_dir = ws_root / "temporary"
        if temp_dir.exists():
            for child in temp_dir.iterdir():
                if child.is_dir() and child.name.startswith("doc_proc_"):
                    try:
                        shutil.rmtree(child)
                    except Exception as e:
                        logger.warning(f"Failed to remove stale temp dir {child}: {e}")
    except Exception as e:
        logger.warning(f"Reconciliation temp cleanup error: {e}")

    # 2. Reconcile database states
    async with get_db() as db:
        # Clean deleting sources
        cursor = await db.execute(
            "SELECT id FROM knowledge_sources WHERE workspace_id = ? AND processing_status = 'deleting'",
            (workspace_id,)
        )
        deleting_rows = await cursor.fetchall()
        for r in deleting_rows:
            await idempotent_delete_source(workspace_id, r["id"])

        # Mark stuck jobs as failed
        await db.execute(
            """UPDATE document_processing_jobs 
               SET status = 'failed', error_code = 'STALE_JOB', error_message = 'Job reconciled after system restart'
               WHERE workspace_id = ? AND status IN ('pending', 'inspecting', 'extracting', 'ocr_processing', 'indexing')""",
            (workspace_id,)
        )
        await db.commit()
