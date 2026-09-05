import os
import asyncio
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import chromadb
from fastembed import TextEmbedding
from pypdf import PdfReader
from cognishift.app.config import settings

class RecursiveCharacterTextSplitter:
    """Zero-dependency pure-Python recursive text splitter."""
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 80):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end >= len(text):
                chunks.append(text[start:].strip())
                break
            split_at = -1
            for sep in ['\n\n', '\n', '. ', ' ']:
                idx = text.rfind(sep, start, end)
                if idx != -1:
                    split_at = idx + len(sep)
                    break
            if split_at == -1 or split_at <= start:
                split_at = end
            chunk = text[start:split_at].strip()
            if chunk:
                chunks.append(chunk)
            start = max(start + 1, split_at - self.chunk_overlap)
        return [c for c in chunks if c]

# Industrial-grade recursive text splitter with overlap
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)

# Initialize ChromaDB locally
chroma_client = chromadb.PersistentClient(path=str(settings.chroma_path))

# Initialize FastEmbed locally (CPU optimized, 100% offline in sovereign mode)
os.environ["HF_HUB_OFFLINE"] = "1"
try:
    embedding_model = TextEmbedding(
        model_name="BAAI/bge-small-en-v1.5",
        cache_dir=str(settings.fastembed_cache_dir),
        local_files_only=settings.fastembed_offline,
    )
except Exception:
    embedding_model = TextEmbedding(
        model_name="BAAI/bge-small-en-v1.5"
    )


async def process_pdf(file_path: str, workspace_id: int, source_id: int, filename: str = "") -> int:
    """
    Reads a PDF, applies Phase 5 multimodal processing (native text triage, local OCR fallback),
    splits text into page-aware chunks, and stores embeddings with provenance in ChromaDB.
    Returns the total number of chunks processed.
    """
    from cognishift.core.document_processing.service import DocumentProcessingService
    service = DocumentProcessingService()
    result = await service.process_document(
        workspace_id=workspace_id,
        source_id=source_id,
        file_path=Path(file_path),
        filename=filename
    )
    return result.get("chunk_count", 0)


async def purge_knowledge_source(workspace_id: int, source_id: int) -> bool:
    """
    Purges all vector embeddings belonging to source_id from ChromaDB.
    Verifies removal off-thread. Raises RuntimeError if Chroma deletion fails.
    """
    collection_name = f"workspace_{workspace_id}"
    try:
        collection = chroma_client.get_collection(name=collection_name)
    except Exception:
        # Collection does not exist; nothing to purge
        return True

    def _delete_and_verify() -> bool:
        sid_int = int(source_id)
        collection.delete(where={"source_id": sid_int})
        # Verify chunks are removed
        remaining = collection.get(where={"source_id": sid_int}, limit=1)
        if remaining and remaining.get("ids") and len(remaining["ids"]) > 0:
            raise RuntimeError(f"Chroma purge verification failed: chunks still present for source_id {source_id}")
        return True

    await asyncio.to_thread(_delete_and_verify)
    return True


MAX_DISTANCE_THRESHOLD = 0.75


async def retrieve_context(
    workspace_id: int,
    query: str,
    top_k: int = 3,
    allowed_source_ids: Optional[List[int]] = None,
    distance_threshold: float = MAX_DISTANCE_THRESHOLD
) -> str:
    """
    Searches ChromaDB for the given query within the workspace.
    FAIL-CLOSED: If allowed_source_ids is an empty list, returns empty context immediately.
    Server-side metadata filtering enforces agent knowledge boundary and active processing version.
    """
    if allowed_source_ids is not None and len(allowed_source_ids) == 0:
        return ""

    collection_name = f"workspace_{workspace_id}"
    try:
        collection = chroma_client.get_collection(name=collection_name)
        count = await asyncio.to_thread(collection.count)
        if count == 0:
            return ""
    except Exception:
        return ""

    effective_k = min(top_k, count)
    if effective_k <= 0:
        return ""

    # Look up authoritative active processing versions from SQLite
    version_map: Dict[int, Optional[str]] = {}
    try:
        from cognishift.app.db.database import get_db
        async with get_db() as db:
            query_sql = "SELECT id, active_processing_version FROM knowledge_sources WHERE workspace_id = ?"
            params: list = [workspace_id]
            if allowed_source_ids is not None:
                placeholders = ",".join("?" for _ in allowed_source_ids)
                query_sql += f" AND id IN ({placeholders})"
                params.extend([int(sid) for sid in allowed_source_ids])
            cursor = await db.execute(query_sql, params)
            rows = await cursor.fetchall()
            for r in rows:
                if r["active_processing_version"]:
                    version_map[r["id"]] = r["active_processing_version"]
    except Exception:
        pass

    # Build Chroma where_filter enforcing active version pairs
    where_filter = None
    if allowed_source_ids is not None:
        clean_ids = [int(sid) for sid in allowed_source_ids]
        conditions: List[Dict[str, Any]] = []
        for sid in clean_ids:
            if sid in version_map:
                conditions.append({
                    "$and": [
                        {"source_id": sid},
                        {"processing_version": str(version_map[sid])}
                    ]
                })
            else:
                conditions.append({"source_id": sid})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$or": conditions}
    elif version_map:
        conditions = [
            {
                "$and": [
                    {"source_id": sid},
                    {"processing_version": str(v)}
                ]
            }
            for sid, v in version_map.items()
        ]
        if len(conditions) == 1:
            where_filter = conditions[0]
        else:
            where_filter = {"$or": conditions}

    try:
        def _get_q_emb():
            raw = list(embedding_model.embed([query]))[0]
            return raw.tolist() if hasattr(raw, "tolist") else [float(x) for x in raw]
            
        q_vec = await asyncio.to_thread(_get_q_emb)
        query_kwargs = {
            "query_embeddings": [q_vec],
            "n_results": effective_k
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = await asyncio.to_thread(
            collection.query,
            **query_kwargs
        )
    except Exception:
        return ""

    if not results or not results.get('documents') or not results['documents'][0]:
        return ""

    from cognishift.core.document_processing.provenance import (
        wrap_document_data_for_prompt,
        format_grounded_citation
    )

    # Filter chunks based on distance threshold
    distances = results.get('distances', [[]])[0] if results.get('distances') else []
    valid_chunks = []
    for i, doc in enumerate(results['documents'][0]):
        dist = distances[i] if i < len(distances) else None
        if dist is not None and dist > distance_threshold:
            continue
        valid_chunks.append((doc, i))

    if not valid_chunks:
        return ""

    formatted_context = "--- RETRIEVED CONTEXT ---\n"
    for doc, i in valid_chunks:
        meta = results['metadatas'][0][i] if results.get('metadatas') and len(results['metadatas']) > 0 else {}
        citation = format_grounded_citation(meta)
        wrapped_doc = wrap_document_data_for_prompt(doc, meta)
        formatted_context += f"{citation}\n{wrapped_doc}\n\n"

    return formatted_context.strip()
