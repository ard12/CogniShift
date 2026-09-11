"""
Evidence Fusion & Query Intent Routing Subsystem.
Implements Reciprocal Rank Fusion (RRF) and dynamic intent-aware channel weighting
for hybrid multimodal retrieval in CogniShift.
"""
import re
from typing import List, Dict, Any, Tuple, Optional
from cognishift.app.config import settings
from cognishift.core.visual_rag.schemas import VisualSearchResult, FusedPageEvidence

# Regex patterns for query intent triage
RCA_PATTERN = re.compile(
    r"\b(rca|root\s*cause|failure\s*investigation|why\s*did\s*it\s*fail|why\s*did\s*the\s*system\s*trip|trip\s*investigation|incident|anomaly|troubleshoot)\b",
    re.IGNORECASE
)

VISUAL_LAYOUT_PATTERN = re.compile(
    r"\b(p&id|pid|diagram|schematic|blueprint|flowchart|piping|drawing|table|chart|curve|plot|graph|look\s*at\s*page|figure|nameplate)\b",
    re.IGNORECASE
)


class QueryIntentWeighting:
    """Analyzes user query and dynamically assigns channel weights."""

    @classmethod
    def determine_weights(cls, query: str) -> Tuple[str, float, float]:
        """
        Returns (intent_type, weight_text, weight_visual).
        Guarantees RCA queries get balanced dual-channel weights.
        """
        clean_q = query.strip().lower()

        # RCA intent takes precedence: root causes span both text logs and visual P&IDs
        if RCA_PATTERN.search(clean_q):
            return "rca", 0.5, 0.5

        # Visual / Layout intent
        if VISUAL_LAYOUT_PATTERN.search(clean_q):
            return "visual", 0.3, 0.7

        # Default text-dominant intent
        return "text", 0.8, 0.2


class EvidenceFusion:
    """Fuses multi-channel candidate pages using Reciprocal Rank Fusion (RRF)."""

    def __init__(self, rrf_k: Optional[int] = None):
        self.rrf_k = rrf_k or getattr(settings, "hybrid_rrf_k", 60)

    def fuse(
        self,
        text_items: List[Dict[str, Any]],
        visual_results: List[VisualSearchResult],
        query: str
    ) -> List[FusedPageEvidence]:
        """
        Fuses ranked text chunks and ColPali visual candidate pages into a unified ranking.
        """
        intent_type, w_text, w_vis = QueryIntentWeighting.determine_weights(query)

        # 1. Group text chunks by (source_id, page_number)
        text_pages: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for rank_idx, item in enumerate(text_items, start=1):
            sid = item.get("source_id")
            p_num = item.get("page", 1)
            key = (sid, p_num)
            if key not in text_pages:
                text_pages[key] = {
                    "source_id": sid,
                    "page_number": p_num,
                    "filename": item.get("filename", ""),
                    "processing_version": item.get("meta", {}).get("processing_version", "v1"),
                    "snippets": [item.get("doc", "")],
                    "best_score": item.get("score", 0.0),
                    "best_rank": rank_idx
                }
            else:
                text_pages[key]["snippets"].append(item.get("doc", ""))
                if item.get("score", 0.0) > text_pages[key]["best_score"]:
                    text_pages[key]["best_score"] = item.get("score", 0.0)
                    text_pages[key]["best_rank"] = min(text_pages[key]["best_rank"], rank_idx)

        # 2. Map visual results
        vis_pages: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for rank_idx, vr in enumerate(visual_results, start=1):
            key = (vr.source_id, vr.page_number)
            vis_pages[key] = {
                "source_id": vr.source_id,
                "workspace_id": vr.workspace_id,
                "page_number": vr.page_number,
                "filename": vr.filename,
                "processing_version": vr.processing_version,
                "score": vr.score,
                "rank": rank_idx
            }

        # 3. Collect union of all candidate pages
        all_keys = set(text_pages.keys()) | set(vis_pages.keys())
        fused_candidates: List[FusedPageEvidence] = []

        penalty_text_rank = len(text_items) + 10
        penalty_vis_rank = len(visual_results) + 10

        for key in all_keys:
            sid, p_num = key
            t_data = text_pages.get(key)
            v_data = vis_pages.get(key)

            # Determine coordinates and filename
            ws_id = (v_data.get("workspace_id") if v_data else None) or (t_data.get("meta", {}).get("workspace_id") if t_data else None) or 1
            f_name = (v_data["filename"] if v_data else "") or (t_data["filename"] if t_data else "")
            p_ver = (v_data["processing_version"] if v_data else "") or (t_data["processing_version"] if t_data else "v1")

            t_rank = t_data["best_rank"] if t_data else penalty_text_rank
            v_rank = v_data["rank"] if v_data else penalty_vis_rank

            t_score = t_data["best_score"] if t_data else None
            v_score = v_data["score"] if v_data else None

            # Reciprocal Rank Fusion formula
            rrf_score = (w_text / (self.rrf_k + t_rank)) + (w_vis / (self.rrf_k + v_rank))

            # Channel attribution
            if t_data and v_data:
                channel = "hybrid"
                citation = f"[{f_name} | Page {p_num} | HYBRID]"
            elif v_data:
                channel = "visual"
                citation = f"[{f_name} | Page {p_num} | VISUAL]"
            else:
                channel = "text"
                citation = f"[{f_name} | Page {p_num} | NATIVE]"

            fused_candidates.append(
                FusedPageEvidence(
                    workspace_id=ws_id,
                    source_id=sid,
                    processing_version=p_ver,
                    page_number=p_num,
                    filename=f_name,
                    retrieval_channel=channel,
                    text_score=t_score,
                    visual_score=v_score,
                    fused_score=rrf_score,
                    text_snippets=t_data["snippets"] if t_data else [],
                    citation=citation
                )
            )

        # Sort candidates descending by fused RRF score
        fused_candidates.sort(key=lambda c: c.fused_score, reverse=True)
        return fused_candidates
