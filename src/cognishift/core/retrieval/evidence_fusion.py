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
    r"\b(p&id|pid|diagram|schematic|blueprint|flowchart|piping|drawing|curve|plot|graph|look\s*at\s*page|figure|nameplate|assembly|cross\s*section|nozzle)\b",
    re.IGNORECASE
)

TABLE_PATTERN = re.compile(
    r"\b(table|grid|column|datasheet|specification|tube\s*id|setpoint|thickness\s*log|inspection\s*sheet|checklist)\b",
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

        # Dense table intent
        if TABLE_PATTERN.search(clean_q):
            return "table", 0.4, 0.6

        # Default text-dominant intent
        return "text", 0.8, 0.2


class EvidenceFusion:
    """
    Fuses multi-channel candidate pages using confidence-aware Reciprocal Rank Fusion (RRF).
    Guarantees that high-confidence text matches are not perturbed by visual noise,
    while elevating visual candidates when queries target layout, tables, or diagrams.
    """

    def __init__(
        self,
        rrf_k: Optional[int] = None,
        mode: str = "confidence_gated",
        weight_text_override: Optional[float] = None,
        weight_visual_override: Optional[float] = None,
        missing_penalty: bool = False
    ):
        self.rrf_k = rrf_k or getattr(settings, "hybrid_rrf_k", 10)
        self.mode = mode
        self.weight_text_override = weight_text_override
        self.weight_visual_override = weight_visual_override
        self.missing_penalty = missing_penalty

    def fuse(
        self,
        text_items: List[Dict[str, Any]],
        visual_results: List[VisualSearchResult],
        query: str
    ) -> List[FusedPageEvidence]:
        """
        Fuses ranked text chunks and ColPali visual candidate pages into a unified ranking.
        """
        intent_type, default_w_text, default_w_vis = QueryIntentWeighting.determine_weights(query)
        w_text = self.weight_text_override if self.weight_text_override is not None else default_w_text
        w_vis = self.weight_visual_override if self.weight_visual_override is not None else default_w_vis

        # 1. Group text chunks by (source_id, page_number)        # 1. Map text results
        text_pages: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for rank_idx, item in enumerate(text_items, start=1):
            sid = item.get("source_id") or item.get("meta", {}).get("source_id")
            p_num = item.get("page") or item.get("meta", {}).get("page") or 1
            if not sid:
                continue
            key = (int(sid), int(p_num))

            # Distinguish distance (lower is better) vs similarity (higher is better)
            if "distance" in item and item["distance"] is not None:
                dist_val = float(item["distance"])
                sim_val = float(item.get("similarity", item.get("score", max(0.0, 1.0 - (dist_val / 2.0)))))
            else:
                # Fallback: if only score is present
                raw_score = float(item.get("score", 0.5))
                sim_val = raw_score
                dist_val = max(0.0, (1.0 - sim_val) * 2.0)

            if key not in text_pages:
                text_pages[key] = {
                    "source_id": int(sid),
                    "page_number": int(p_num),
                    "filename": item.get("filename", ""),
                    "processing_version": item.get("meta", {}).get("processing_version", "v1"),
                    "snippets": [item.get("doc", "")],
                    "best_distance": dist_val,
                    "best_similarity": sim_val,
                    "best_score": sim_val,
                    "best_rank": rank_idx
                }
            else:
                text_pages[key]["snippets"].append(item.get("doc", ""))
                # For page aggregation: best chunk is the one with minimum distance (maximum similarity)
                if dist_val < text_pages[key]["best_distance"]:
                    text_pages[key]["best_distance"] = dist_val
                    text_pages[key]["best_similarity"] = sim_val
                    text_pages[key]["best_score"] = sim_val
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
                "score": vr.score, # MaxSim score
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

            t_dist = t_data.get("best_distance") if t_data else None
            t_sim = t_data.get("best_similarity") if t_data else None
            t_score = t_sim
            v_score = v_data["score"] if v_data else None

            # Calculate confidence signals
            # Text distance: 0.0 is exact match, 0.78 is threshold
            c_text = 0.0
            if t_dist is not None:
                c_text = max(0.0, 1.0 - (float(t_dist) / 0.78))

            # Visual MaxSim: > 10 is very strong, 3-8 moderate
            c_vis = 0.0
            if v_score is not None:
                c_vis = min(1.0, max(0.0, (float(v_score) - 2.0) / 10.0))

            # Determine rank scores
            if self.missing_penalty:
                t_rank = t_data["best_rank"] if t_data else penalty_text_rank
                v_rank = v_data["rank"] if v_data else penalty_vis_rank
                score_text = w_text / (self.rrf_k + t_rank)
                score_vis = w_vis / (self.rrf_k + v_rank)
            else:
                # True standard RRF: 0 contribution if not retrieved in channel
                score_text = (w_text / (self.rrf_k + t_data["best_rank"])) if t_data else 0.0
                score_vis = (w_vis / (self.rrf_k + v_data["rank"])) if v_data else 0.0

            # Confidence-gated modulation
            if self.mode == "confidence_gated":
                # If text match is very confident and query is text-dominant, boost text
                if c_text >= 0.70 and intent_type == "text":
                    score_text *= (1.0 + 1.5 * c_text)
                # If query is visual/table or text match is weak, boost visual
                elif intent_type in ["visual", "table"] or c_text < 0.35:
                    score_vis *= (1.0 + 1.5 * c_vis)
                elif intent_type == "rca":
                    # Balanced dual-channel modulation for RCA
                    if c_text >= 0.60:
                        score_text *= (1.0 + c_text)
                    if c_vis >= 0.50:
                        score_vis *= (1.0 + c_vis)

            # Winner Preservation Rule (from Benchmark V2 audit):
            # If visual top-1 is strongly separated on layout/P&ID queries and text lacks dominant confidence,
            # ensure the visual top-1 candidate is preserved against generic text demotion.
            if visual_results and key == (visual_results[0].source_id, visual_results[0].page_number):
                sep = visual_results[0].score - (visual_results[1].score if len(visual_results) > 1 else 0.0)
                is_visual_query = (intent_type in ["visual", "table"] or bool(VISUAL_LAYOUT_PATTERN.search(query)))
                if is_visual_query and (sep >= 1.5 or visual_results[0].score >= 8.0) and c_text < 0.80:
                    score_vis *= 2.0

            rrf_score = score_text + score_vis

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
                    text_distance=t_dist,
                    visual_score=v_score,
                    fused_score=rrf_score,
                    text_snippets=t_data["snippets"] if t_data else [],
                    citation=citation
                )
            )

        # Sort candidates descending by fused RRF score
        fused_candidates.sort(key=lambda c: c.fused_score, reverse=True)

        # For RCA queries, guarantee modality diversity in the returned ranking:
        # Prevent 5 identical text pages from crowding out a top-ranked visual schematic.
        if intent_type == "rca" and len(fused_candidates) > 3:
            diverse: List[FusedPageEvidence] = []
            has_vis = any(c.retrieval_channel in ("visual", "hybrid") for c in fused_candidates)
            if has_vis:
                first_vis = next((c for c in fused_candidates if c.retrieval_channel in ("visual", "hybrid")), None)
                first_txt = next((c for c in fused_candidates if c.retrieval_channel in ("text", "hybrid")), None)
                if first_txt:
                    diverse.append(first_txt)
                if first_vis and first_vis not in diverse:
                    diverse.append(first_vis)
                for c in fused_candidates:
                    if c not in diverse:
                        diverse.append(c)
                return diverse

        return fused_candidates

