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
from cognishift.core.retrieval.visual_inspector import VisualEvidenceInspector, get_visual_inspector
from cognishift.core.document_processing.provenance import wrap_document_data_for_prompt

logger = logging.getLogger(__name__)


class HybridDocumentRetriever:
    """End-to-end Hybrid Multimodal Retriever."""

    def __init__(
        self,
        text_retriever: Optional[TextRetriever] = None,
        visual_retriever: Optional[VisualRetriever] = None,
        vision_service: Optional[VisionProcessingService] = None,
        allow_simulation: bool = False,
        inspector: Optional[VisualEvidenceInspector] = None
    ):
        self.text_retriever = text_retriever or TextRetriever()
        self.visual_retriever = visual_retriever or VisualRetriever(allow_simulation=allow_simulation)
        self.vision_service = vision_service or VisionProcessingService()
        self.fusion = EvidenceFusion()
        self.verifier = get_page_verifier()
        self.allow_simulation = allow_simulation
        self.inspector = inspector or VisualEvidenceInspector(
            vision_service=self.vision_service,
            verifier=self.verifier
        )

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

        for i in range(max_vlm_pages):
            cand = fused_candidates[i]
            # Only inspect pages with visual relevance
            if cand.retrieval_channel in ["visual", "hybrid"] or needs_visual_inspection:
                try:
                    insp_res = await self.inspector.inspect_page(
                        workspace_id=workspace_id,
                        source_id=cand.source_id,
                        page_number=cand.page_number,
                        filename=cand.filename,
                        visual_score=cand.visual_score or 0.0,
                        processing_version=cand.processing_version,
                        query=query
                    )
                    if insp_res and insp_res.vlm_observation:
                        cand.vlm_observation = insp_res.vlm_observation
                        cand.corroboration_results = insp_res.corroboration_results
                        cand.ocr_corroborated = insp_res.ocr_corroborated
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
                raw_text = "\n".join(cand.text_snippets)
                cand_meta = {
                    "filename": cand.filename,
                    "page_number": cand.page_number,
                    "page": cand.page_number,
                    "source_id": cand.source_id,
                    "processing_version": cand.processing_version,
                }
                wrapped_text = wrap_document_data_for_prompt(raw_text, cand_meta)
                block_lines.append(wrapped_text)

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
