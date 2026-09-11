"""
Text Retriever Subsystem for CogniShift.
Manages FastEmbed + ChromaDB vector querying, calibrated distance thresholding,
active processing version enforcement, and text chunk provenance.
"""
import asyncio
import logging
from typing import List, Tuple, Optional, Dict, Any

from cognishift.app.config import settings
from cognishift.core.retriever import chroma_client, embedding_model
from cognishift.core.document_processing.provenance import (
    wrap_document_data_for_prompt,
    format_grounded_citation
)

logger = logging.getLogger(__name__)


class TextRetriever:
    """Encapsulates FastEmbed + ChromaDB text semantic retrieval."""

    async def retrieve(
        self,
        workspace_id: int,
        query: str,
        top_k: int = 3,
        allowed_source_ids: Optional[List[int]] = None,
        distance_threshold: Optional[float] = None
    ) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Executes text retrieval over ChromaDB.
        Returns:
            (formatted_context_str, retrieved_metadatas, ranked_items)
            where ranked_items is a list of dicts with keys:
            {'doc': str, 'meta': dict, 'distance': float, 'score': float, 'page': int, 'source_id': int}
        """
        if allowed_source_ids is not None and len(allowed_source_ids) == 0:
            return "", [], []

        collection_name = f"workspace_{workspace_id}"
        try:
            collection = chroma_client.get_collection(name=collection_name)
            count = await asyncio.to_thread(collection.count)
            if count == 0:
                return "", [], []
        except Exception:
            return "", [], []

        effective_k = min(top_k, count)
        if effective_k <= 0:
            return "", [], []

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

            results = await asyncio.to_thread(collection.query, **query_kwargs)
        except Exception as e:
            logger.warning(f"Chroma text query error: {e}")
            return "", [], []

        if not results or not results.get("documents") or not results["documents"][0]:
            return "", [], []

        max_dist = distance_threshold if distance_threshold is not None else getattr(settings, "semantic_retrieval_max_distance", 0.78)
        formatted_context_parts = []
        retrieved_metadatas = []
        ranked_items = []
        distances = results.get("distances", [[]])[0] if results.get("distances") else []
        seen_chunk_keys = set()

        for i, doc in enumerate(results["documents"][0]):
            dist = distances[i] if i < len(distances) else 0.0
            if not doc or len(doc.strip()) < 25:
                continue
            if dist is not None and dist <= 2.0 and dist > max_dist:
                logger.info(f"TextRetriever discarded distant chunk: distance={dist:.4f} > {max_dist:.4f}")
                continue

            meta = results["metadatas"][0][i] if results.get("metadatas") and len(results["metadatas"]) > 0 else {}
            chunk_key = (
                meta.get("source_id"),
                meta.get("sheet_name"),
                meta.get("row_start"),
                meta.get("row_end"),
                meta.get("segment_index")
            )
            if any(v is not None for v in chunk_key[2:]):
                if chunk_key in seen_chunk_keys:
                    continue
                seen_chunk_keys.add(chunk_key)

            citation = format_grounded_citation(meta)
            wrapped_doc = wrap_document_data_for_prompt(doc, meta)
            formatted_context_parts.append(f"{citation}\n{wrapped_doc}")
            retrieved_metadatas.append(meta)

            # Similarity score derived from squared L2 distance (bounded 0..1 for unit vectors)
            sim_score = max(0.0, 1.0 - (dist / 2.0))
            page_num = meta.get("page") or meta.get("page_number") or 1
            fname = (
                meta.get("filename")
                or meta.get("document")
                or meta.get("document_name")
                or meta.get("original_filename")
                or meta.get("name")
                or ""
            )
            ranked_items.append({
                "doc": doc,
                "meta": meta,
                "distance": dist,
                "score": sim_score,
                "page": int(page_num),
                "source_id": meta.get("source_id"),
                "filename": fname
            })

        formatted_context = ""
        if formatted_context_parts:
            formatted_context = "--- RETRIEVED CONTEXT ---\n" + "\n\n".join(formatted_context_parts)

        return formatted_context.strip(), retrieved_metadatas, ranked_items
