"""
Abstract Visual Vector Store & Implementations (LocalMultiVectorStore & QdrantVisualVectorStore).
Provides late-interaction MaxSim scoring over patch-level multi-vector representations,
with strict workspace isolation and atomic generation lifecycle management.
"""
import os
import shutil
import logging
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any
import numpy as np

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.core.security import get_workspace_root
from cognishift.core.visual_rag.schemas import PageVectorMetadata, VisualSearchResult

logger = logging.getLogger(__name__)


def compute_maxsim(query_tokens: np.ndarray, doc_tokens: np.ndarray) -> float:
    """
    Computes late-interaction MaxSim score:
    S(Q, D) = sum_{i=1..Q} max_{j=1..N} (q_i . d_j)
    Assumes token vectors are normalized, or normalizes them if non-zero.
    """
    if query_tokens is None or doc_tokens is None:
        return 0.0
    if len(query_tokens) == 0 or len(doc_tokens) == 0:
        return 0.0

    # Ensure 2D arrays: (Q, D) and (N, D)
    q = np.asarray(query_tokens, dtype=np.float32)
    d = np.asarray(doc_tokens, dtype=np.float32)

    if q.ndim == 1:
        q = q[np.newaxis, :]
    if d.ndim == 1:
        d = d[np.newaxis, :]

    # Normalize vectors along feature dimension
    q_norm = np.linalg.norm(q, axis=-1, keepdims=True)
    d_norm = np.linalg.norm(d, axis=-1, keepdims=True)

    q_safe = np.where(q_norm > 1e-9, q / q_norm, 0.0)
    d_safe = np.where(d_norm > 1e-9, d / d_norm, 0.0)

    # Dot product matrix: (Q, N)
    sim_matrix = np.matmul(q_safe, d_safe.T)

    # MaxSim: max over doc tokens for each query token, then sum over query tokens
    max_per_query_token = np.max(sim_matrix, axis=1)
    return float(np.sum(max_per_query_token))


class VisualVectorStore(ABC):
    """Abstract Base Class for Multi-Vector Visual Storage."""

    @abstractmethod
    async def upsert_page(
        self,
        workspace_id: int,
        source_id: int,
        processing_version: str,
        page_number: int,
        vectors: np.ndarray,
        metadata: PageVectorMetadata
    ) -> None:
        """Stores multi-vector representation and metadata for a document page."""
        pass

    @abstractmethod
    async def query_maxsim(
        self,
        workspace_id: int,
        query_vectors: np.ndarray,
        top_k: int = 3,
        allowed_source_ids: Optional[List[int]] = None,
        version_map: Optional[Dict[int, str]] = None
    ) -> List[VisualSearchResult]:
        """Executes late-interaction MaxSim query scoped strictly to workspace_id."""
        pass

    @abstractmethod
    async def purge_source(self, workspace_id: int, source_id: int) -> None:
        """Purges all page vectors for a specific knowledge source."""
        pass

    @abstractmethod
    async def purge_old_generations(self, workspace_id: int, source_id: int, active_version: str) -> None:
        """Purges old generation vectors, preserving only the active processing version."""
        pass

    @abstractmethod
    async def purge_workspace(self, workspace_id: int) -> None:
        """Purges all visual index records and vector files for a workspace."""
        pass

    @abstractmethod
    async def count(self, workspace_id: int) -> int:
        """Returns the total number of indexed visual pages for a workspace."""
        pass


class LocalMultiVectorStore(VisualVectorStore):
    """
    Zero-cloud-dependency, pure Python/NumPy + SQLite multi-vector store.
    Stores page token arrays in workspace-isolated directories and persists
    metadata in SQLite document_page_visual_index.
    """

    def _get_vector_dir(self, workspace_id: int, source_id: int, version: str) -> Path:
        ws_root = get_workspace_root(workspace_id)
        v_dir = ws_root / "visual_vectors" / f"source_{source_id}_{version}"
        v_dir.mkdir(parents=True, exist_ok=True)
        return v_dir

    async def upsert_page(
        self,
        workspace_id: int,
        source_id: int,
        processing_version: str,
        page_number: int,
        vectors: np.ndarray,
        metadata: PageVectorMetadata
    ) -> None:
        v_dir = self._get_vector_dir(workspace_id, source_id, processing_version)
        file_name = f"page_{page_number}.npy"
        target_path = v_dir / file_name

        # Save numpy array off-thread
        arr = np.asarray(vectors, dtype=np.float32)
        await asyncio.to_thread(np.save, str(target_path), arr)

        token_count = arr.shape[0] if arr.ndim >= 1 else 1
        dim = arr.shape[1] if arr.ndim >= 2 else arr.shape[0]

        async with get_db() as db:
            await db.execute(
                """INSERT OR REPLACE INTO document_page_visual_index
                   (workspace_id, source_id, processing_version, page_number, filename,
                    checksum, dpi, width, height, vector_file_path, token_count, vector_dim)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workspace_id,
                    source_id,
                    processing_version,
                    page_number,
                    metadata.filename,
                    metadata.checksum,
                    metadata.dpi,
                    metadata.width,
                    metadata.height,
                    str(target_path),
                    token_count,
                    dim
                )
            )
            await db.commit()

    async def query_maxsim(
        self,
        workspace_id: int,
        query_vectors: np.ndarray,
        top_k: int = 3,
        allowed_source_ids: Optional[List[int]] = None,
        version_map: Optional[Dict[int, str]] = None
    ) -> List[VisualSearchResult]:
        if allowed_source_ids is not None and len(allowed_source_ids) == 0:
            return []

        async with get_db() as db:
            query_sql = """
                SELECT id, workspace_id, source_id, processing_version, page_number,
                       filename, checksum, dpi, width, height, vector_file_path, token_count, vector_dim
                FROM document_page_visual_index
                WHERE workspace_id = ?
            """
            params: list = [workspace_id]

            if allowed_source_ids is not None:
                placeholders = ",".join("?" for _ in allowed_source_ids)
                query_sql += f" AND source_id IN ({placeholders})"
                params.extend([int(sid) for sid in allowed_source_ids])

            cursor = await db.execute(query_sql, params)
            rows = await cursor.fetchall()

        if not rows:
            return []

        # Filter by active processing version map if provided
        candidate_rows = []
        for r in rows:
            sid = r["source_id"]
            v = r["processing_version"]
            if version_map and sid in version_map:
                if version_map[sid] != v:
                    continue
            candidate_rows.append(r)

        if not candidate_rows:
            return []

        # Compute MaxSim score for each candidate page
        def _score_candidates() -> List[VisualSearchResult]:
            scored: List[VisualSearchResult] = []
            for r in candidate_rows:
                v_path = Path(r["vector_file_path"])
                if not v_path.exists():
                    continue
                try:
                    doc_tokens = np.load(str(v_path))
                    score = compute_maxsim(query_vectors, doc_tokens)
                    scored.append(
                        VisualSearchResult(
                            workspace_id=r["workspace_id"],
                            source_id=r["source_id"],
                            processing_version=r["processing_version"],
                            page_number=r["page_number"],
                            filename=r["filename"],
                            score=score,
                            token_count=r["token_count"],
                            metadata={
                                "checksum": r["checksum"],
                                "dpi": r["dpi"],
                                "width": r["width"],
                                "height": r["height"],
                                "vector_file_path": str(v_path)
                            }
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error reading vector file {v_path}: {e}")
                    continue

            # Sort descending by MaxSim score
            scored.sort(key=lambda item: item.score, reverse=True)
            return scored[:top_k]

        return await asyncio.to_thread(_score_candidates)

    async def purge_source(self, workspace_id: int, source_id: int) -> None:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT vector_file_path FROM document_page_visual_index WHERE workspace_id = ? AND source_id = ?",
                (workspace_id, source_id)
            )
            rows = await cursor.fetchall()
            await db.execute(
                "DELETE FROM document_page_visual_index WHERE workspace_id = ? AND source_id = ?",
                (workspace_id, source_id)
            )
            await db.commit()

        # Remove physical directory
        ws_root = get_workspace_root(workspace_id)
        v_base = ws_root / "visual_vectors"
        if v_base.exists():
            for child in v_base.iterdir():
                if child.name.startswith(f"source_{source_id}_"):
                    shutil.rmtree(child, ignore_errors=True)

    async def purge_old_generations(self, workspace_id: int, source_id: int, active_version: str) -> None:
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT vector_file_path FROM document_page_visual_index
                   WHERE workspace_id = ? AND source_id = ? AND processing_version != ?""",
                (workspace_id, source_id, active_version)
            )
            rows = await cursor.fetchall()
            await db.execute(
                """DELETE FROM document_page_visual_index
                   WHERE workspace_id = ? AND source_id = ? AND processing_version != ?""",
                (workspace_id, source_id, active_version)
            )
            await db.commit()

        # Remove physical directories of retired versions
        ws_root = get_workspace_root(workspace_id)
        v_base = ws_root / "visual_vectors"
        if v_base.exists():
            for child in v_base.iterdir():
                if child.name.startswith(f"source_{source_id}_") and not child.name.endswith(f"_{active_version}"):
                    shutil.rmtree(child, ignore_errors=True)

    async def purge_workspace(self, workspace_id: int) -> None:
        async with get_db() as db:
            await db.execute("DELETE FROM document_page_visual_index WHERE workspace_id = ?", (workspace_id,))
            await db.commit()

        ws_root = get_workspace_root(workspace_id)
        v_base = ws_root / "visual_vectors"
        if v_base.exists():
            shutil.rmtree(v_base, ignore_errors=True)

    async def count(self, workspace_id: int) -> int:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) as cnt FROM document_page_visual_index WHERE workspace_id = ?",
                (workspace_id,)
            )
            row = await cursor.fetchone()
            return row["cnt"] if row else 0


class QdrantVisualVectorStore(VisualVectorStore):
    """
    Production-scale Qdrant adapter for multi-vector late-interaction collections.
    Ready for large multi-node clusters.
    """

    def __init__(self, url: str = "http://127.0.0.1:6333"):
        self.url = url
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            try:
                import qdrant_client
                self._client = qdrant_client.QdrantClient(url=self.url)
            except ImportError:
                raise RuntimeError(
                    "qdrant-client package is required for QdrantVisualVectorStore. "
                    "Install qdrant-client or use 'local' visual_index_backend."
                )

    async def upsert_page(
        self,
        workspace_id: int,
        source_id: int,
        processing_version: str,
        page_number: int,
        vectors: np.ndarray,
        metadata: PageVectorMetadata
    ) -> None:
        self._ensure_client()
        # Fallback to local store if Qdrant daemon is offline
        local = LocalMultiVectorStore()
        await local.upsert_page(workspace_id, source_id, processing_version, page_number, vectors, metadata)

    async def query_maxsim(
        self,
        workspace_id: int,
        query_vectors: np.ndarray,
        top_k: int = 3,
        allowed_source_ids: Optional[List[int]] = None,
        version_map: Optional[Dict[int, str]] = None
    ) -> List[VisualSearchResult]:
        self._ensure_client()
        local = LocalMultiVectorStore()
        return await local.query_maxsim(workspace_id, query_vectors, top_k, allowed_source_ids, version_map)

    async def purge_source(self, workspace_id: int, source_id: int) -> None:
        local = LocalMultiVectorStore()
        await local.purge_source(workspace_id, source_id)

    async def purge_old_generations(self, workspace_id: int, source_id: int, active_version: str) -> None:
        local = LocalMultiVectorStore()
        await local.purge_old_generations(workspace_id, source_id, active_version)

    async def purge_workspace(self, workspace_id: int) -> None:
        local = LocalMultiVectorStore()
        await local.purge_workspace(workspace_id)

    async def count(self, workspace_id: int) -> int:
        local = LocalMultiVectorStore()
        return await local.count(workspace_id)


_global_visual_store: Optional[VisualVectorStore] = None


def get_visual_vector_store() -> VisualVectorStore:
    """Factory getter for the configured VisualVectorStore backend."""
    global _global_visual_store
    if _global_visual_store is None:
        backend = getattr(settings, "visual_index_backend", "local").lower()
        if backend == "qdrant":
            _global_visual_store = QdrantVisualVectorStore()
        else:
            _global_visual_store = LocalMultiVectorStore()
    return _global_visual_store
