"""
Visual Retriever Subsystem for CogniShift.
Executes late-interaction MaxSim visual page retrieval over ColPali multi-vector representations.
Guarantees strict workspace isolation, active version enforcement, and graceful fallback.
"""
import asyncio
import logging
from typing import List, Optional, Dict, Any

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.core.visual_rag.schemas import VisualSearchResult
from cognishift.core.visual_rag.vector_store import get_visual_vector_store
from cognishift.core.visual_rag.embedding_provider import get_visual_embedding_provider

logger = logging.getLogger(__name__)


class VisualRetriever:
    """Manages ColPali late-interaction visual page retrieval."""

    def __init__(self, visual_provider: Optional[Any] = None, allow_simulation: bool = False):
        self._custom_provider = visual_provider
        self.allow_simulation = allow_simulation

    async def retrieve(
        self,
        workspace_id: int,
        query: str,
        top_k: int = 3,
        allowed_source_ids: Optional[List[int]] = None
    ) -> List[VisualSearchResult]:
        """
        Executes ColPali MaxSim page search.
        Returns top-K candidate pages. Returns [] if visual RAG is disabled or weights are missing.
        """
        if allowed_source_ids is not None and len(allowed_source_ids) == 0:
            return []

        provider = self._custom_provider or get_visual_embedding_provider(allow_simulation=self.allow_simulation)
        if provider is None or not provider.is_available():
            # Graceful fallback: Visual retrieval is offline or not installed
            return []

        # Resolve authoritative active processing versions
        version_map: Dict[int, str] = {}
        try:
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
        except Exception as e:
            logger.warning(f"Error reading active version map for visual retrieval: {e}")

        try:
            q_vecs = await asyncio.to_thread(provider.embed_query, query)
            v_store = get_visual_vector_store()
            results = await v_store.query_maxsim(
                workspace_id=workspace_id,
                query_vectors=q_vecs,
                top_k=top_k,
                allowed_source_ids=allowed_source_ids,
                version_map=version_map
            )
            return results
        except Exception as e:
            logger.warning(f"Visual retrieval error: {e}")
            return []
