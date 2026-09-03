import os
import asyncio
from pathlib import Path
from typing import List, Tuple, Optional
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

# Initialize FastEmbed locally (CPU optimized)
embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


async def process_pdf(file_path: str, workspace_id: int, source_id: int, filename: str = "") -> int:
    """
    Reads a PDF, splits text into overlapping chunks per page, and stores embeddings in ChromaDB.
    Returns the total number of chunks processed.
    """
    def _extract_and_chunk() -> List[Tuple[str, int, int]]:
        reader = PdfReader(file_path)
        chunks_with_meta = []
        chunk_counter = 0
        for page_idx, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text()
            if not page_text or not page_text.strip():
                continue
            page_chunks = text_splitter.split_text(page_text)
            for chunk in page_chunks:
                clean_chunk = chunk.strip()
                if clean_chunk:
                    chunks_with_meta.append((clean_chunk, page_idx, chunk_counter))
                    chunk_counter += 1
        return chunks_with_meta

    # Run extraction off the main asyncio event loop thread
    chunks_with_meta = await asyncio.to_thread(_extract_and_chunk)
    if not chunks_with_meta:
        return 0

    chunks = [item[0] for item in chunks_with_meta]
    pages = [item[1] for item in chunks_with_meta]
    chunk_indices = [item[2] for item in chunks_with_meta]

    # Run FastEmbed off the main event loop
    def _embed() -> List[List[float]]:
        generator = embedding_model.embed(chunks)
        return [e.tolist() if hasattr(e, "tolist") else [float(x) for x in e] for e in generator]

    embeddings = await asyncio.to_thread(_embed)

    # Store in ChromaDB under a collection specific to the workspace
    collection_name = f"workspace_{workspace_id}"
    collection = chroma_client.get_or_create_collection(name=collection_name)

    doc_name = filename or Path(file_path).name
    ids = [f"doc_{source_id}_chunk_{idx}" for idx in chunk_indices]
    metadatas = [
        {
            "source_id": source_id,
            "workspace_id": workspace_id,
            "filename": doc_name,
            "page": pages[i],
            "chunk_idx": chunk_indices[i]
        }
        for i in range(len(chunks))
    ]

    # Safe batch upsert into ChromaDB to prevent SQLite variable overflow on massive documents
    BATCH_SIZE = 250
    for i in range(0, len(chunks), BATCH_SIZE):
        batch_docs = chunks[i:i + BATCH_SIZE]
        batch_embs = embeddings[i:i + BATCH_SIZE]
        batch_meta = metadatas[i:i + BATCH_SIZE]
        batch_ids = ids[i:i + BATCH_SIZE]
        await asyncio.to_thread(
            collection.upsert,
            documents=batch_docs,
            embeddings=batch_embs,
            metadatas=batch_meta,
            ids=batch_ids
        )

    return len(chunks)


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


async def retrieve_context(
    workspace_id: int,
    query: str,
    top_k: int = 3,
    allowed_source_ids: Optional[List[int]] = None
) -> str:
    """
    Searches ChromaDB for the given query within the workspace.
    FAIL-CLOSED: If allowed_source_ids is an empty list, returns empty context immediately.
    Server-side metadata filtering enforces agent knowledge boundary.
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

    where_filter = None
    if allowed_source_ids is not None:
        clean_ids = [int(sid) for sid in allowed_source_ids]
        if len(clean_ids) == 1:
            where_filter = {"source_id": clean_ids[0]}
        else:
            where_filter = {"source_id": {"$in": clean_ids}}

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

    formatted_context = "--- RETRIEVED CONTEXT ---\n"
    for i, doc in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i] if results.get('metadatas') and len(results['metadatas']) > 0 else {}
        src_name = meta.get('filename') or f"Source {meta.get('source_id', 'unknown')}"
        page = meta.get('page', '?')
        formatted_context += f"[{src_name} | Page {page}]\n{doc}\n\n"

    return formatted_context.strip()
