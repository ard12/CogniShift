"""
Hybrid Multimodal Document Retriever for CogniShift.
Coordinates parallel Text and Visual retrieval, fuses candidates using Reciprocal Rank Fusion,
executes targeted local VLM inspection on top-1/2 pages, and verifies numeric claims via OCR.
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.core.retrieval.text_retriever import TextRetriever
from cognishift.core.retrieval.visual_retriever import VisualRetriever
from cognishift.core.retrieval.evidence_fusion import EvidenceFusion
from cognishift.core.visual_rag.page_cache import render_page_image_on_demand
from cognishift.core.visual_rag.page_verifier import get_page_verifier
from cognishift.core.document_processing.vision_service import VisionProcessingService
from cognishift.core.document_processing.schemas import VisionRequirement

logger = logging.getLogger(__name__)


class HybridDocumentRetriever:
    """End-to-end Hybrid Multimodal Retriever."""

    def __init__(
        self,
        text_retriever: Optional[TextRetriever] = None,
        visual_retriever: Optional[VisualRetriever] = None,
        vision_service: Optional[VisionProcessingService] = None,
        allow_simulation: bool = False
    ):
        self.text_retriever = text_retriever or TextRetriever()
        self.visual_retriever = visual_retriever or VisualRetriever(allow_simulation=allow_simulation)
        self.vision_service = vision_service or VisionProcessingService()
        self.fusion = EvidenceFusion()
        self.verifier = get_page_verifier()
        self.allow_simulation = allow_simulation

    async def retrieve(
        self,
        workspace_id: int,
        query: str,
        top_k: int = 3,
        allowed_source_ids: Optional[List[int]] = None,
        distance_threshold: Optional[float] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Executes hybrid retrieval uniting Text RAG and ColPali visual retrieval.
        Returns (formatted_context_string, retrieved_metadatas).
        """
        # 1. Execute Text Retrieval
        text_ctx, text_metas, text_ranked = await self.text_retriever.retrieve(
            workspace_id=workspace_id,
            query=query,
            top_k=top_k,
            allowed_source_ids=allowed_source_ids,
            distance_threshold=distance_threshold
        )

        # If visual retrieval is completely disabled in settings, return text baseline immediately
        if not getattr(settings, "hybrid_retrieval_enabled", True):
            return text_ctx, text_metas

        # 2. Execute Visual Retrieval (Top-K=3 initially per contract)
        vis_results = await self.visual_retriever.retrieve(
            workspace_id=workspace_id,
            query=query,
            top_k=getattr(settings, "visual_retrieval_top_k", 3),
            allowed_source_ids=allowed_source_ids
        )

        # 3. If no visual results (e.g. weights missing or no visual documents), fall back 100% to text
        if not vis_results:
            return text_ctx, text_metas

        # 4. Evidence Fusion across Text and Visual channels using RRF
        fused_candidates = self.fusion.fuse(
            text_items=text_ranked,
            visual_results=vis_results,
            query=query
        )

        if not fused_candidates:
            return text_ctx, text_metas

        # 5. Targeted VLM Inspection: Strictly bounded to top 1-2 pages (user mandate)
        max_vlm_pages = min(len(fused_candidates), getattr(settings, "visual_vlm_max_pages", 2))
        
        # Check if query requests visual analysis or candidate has strong visual relevance
        query_lower = query.lower()
        needs_visual_inspection = any(
            k in query_lower for k in [
                "diagram", "p&id", "pid", "schematic", "drawing", "table", "chart",
                "figure", "curve", "graph", "look at page", "reading", "rca",
                "root cause", "failure", "trip", "instrument"
            ]
        )

        source_path_cache: Dict[int, Optional[Path]] = {}

        for i in range(max_vlm_pages):
            cand = fused_candidates[i]
            # Only inspect pages with visual relevance
            if cand.retrieval_channel in ["visual", "hybrid"] or needs_visual_inspection:
                sid = cand.source_id
                if sid not in source_path_cache:
                    async with get_db() as db:
                        cursor = await db.execute("SELECT local_path FROM knowledge_sources WHERE id = ?", (sid,))
                        row = await cursor.fetchone()
                        source_path_cache[sid] = Path(row["local_path"]) if row and row["local_path"] else None

                pdf_path = source_path_cache.get(sid)
                if pdf_path and pdf_path.exists():
                    try:
                        # Render page on demand with bounded LRU cache
                        dpi = getattr(settings, "colpali_raster_dpi", 150)
                        page_png = await render_page_image_on_demand(pdf_path, cand.page_number, dpi=dpi)

                        # Targeted local VLM call (Moondream/Qwen-VL)
                        v_obs = await self.vision_service.analyze_document_image(
                            image_bytes=page_png,
                            page_number=cand.page_number,
                            prompt=f"Inspect this page. Identify any visible instruments, equipment tags, readings, table cells, or diagrams relevant to: {query}",
                            requirement=VisionRequirement.OPTIONAL
                        )

                        if v_obs and v_obs.description:
                            cand.vlm_observation = v_obs.description.strip()

                            # Deterministic OCR Corroboration (OCR verified/corroborated semantics)
                            if getattr(settings, "visual_verification_enabled", True):
                                corr_res = await self.verifier.verify_page_claims(
                                    workspace_id=workspace_id,
                                    source_id=cand.source_id,
                                    processing_version=cand.processing_version,
                                    page_number=cand.page_number,
                                    vlm_observation=v_obs.description
                                )
                                cand.corroboration_results = corr_res
                                if corr_res:
                                    cand.ocr_corroborated = all(cr.corroborated for cr in corr_res)
                    except Exception as ve:
                        logger.warning(f"Targeted VLM inspection skipped for page {cand.page_number}: {ve}")

        # 6. Format Consolidated Context and Provenance Citations
        context_blocks = []
        retrieved_metadatas = []

        for cand in fused_candidates[:top_k]:
            block_lines = [f"{cand.citation}"]

            # Attach corroboration summary if available
            if cand.corroboration_results:
                corr_summary = self.verifier.format_corroboration_summary(cand.corroboration_results)
                if corr_summary:
                    block_lines.append(f"[{corr_summary}]")

            # Attach text snippets
            if cand.text_snippets:
                block_lines.append("\n".join(cand.text_snippets))

            # Attach targeted VLM observation
            if cand.vlm_observation:
                block_lines.append(f"--- VISUAL INSPECTION (Page {cand.page_number}) ---\n{cand.vlm_observation}")

            context_blocks.append("\n".join(block_lines))

            retrieved_metadatas.append({
                "workspace_id": cand.workspace_id,
                "source_id": cand.source_id,
                "processing_version": cand.processing_version,
                "page": cand.page_number,
                "page_number": cand.page_number,
                "filename": cand.filename,
                "retrieval_channel": cand.retrieval_channel,
                "fused_score": cand.fused_score,
                "text_score": cand.text_score,
                "visual_score": cand.visual_score,
                "ocr_corroborated": cand.ocr_corroborated,
                "citation": cand.citation
            })

        formatted_context = "--- RETRIEVED MULTIMODAL CONTEXT ---\n" + "\n\n".join(context_blocks)
        return formatted_context.strip(), retrieved_metadatas


_global_hybrid_retriever: Optional[HybridDocumentRetriever] = None


def get_hybrid_retriever(allow_simulation: bool = False) -> HybridDocumentRetriever:
    global _global_hybrid_retriever
    if _global_hybrid_retriever is None:
        _global_hybrid_retriever = HybridDocumentRetriever(allow_simulation=allow_simulation)
    return _global_hybrid_retriever
