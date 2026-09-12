"""RCA Evidence Acquisition Subsystem.

Implements role-aware, multi-channel evidence retrieval across Text RAG, Visual ColPali,
Plant Topology Graph, and verified Telemetry. Enforces explicit evidence contracts
and prevents silent substitution of missing documents or nonexistent assets.
"""
import re
import time
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.core.rca.schemas import (
    EvidenceRole,
    RCAEvidenceItem,
    RCAEvidenceBundle,
    ChannelExecutionHealth,
    EvidenceLocator,
)
from cognishift.core.tool_schemas import SUPPORTED_SIMULATED_TARGETS, resolve_equipment_alias
from cognishift.core.retrieval.text_retriever import TextRetriever
from cognishift.core.retrieval.visual_retriever import VisualRetriever
from cognishift.core.retrieval.evidence_fusion import EvidenceFusion
from cognishift.core.graph_memory import query_graph_context
from cognishift.core.retrieval.visual_inspector import VisualEvidenceInspector, get_visual_inspector, VisualInspectionStatus
from cognishift.core.visual_rag.embedding_provider import get_visual_embedding_provider

logger = logging.getLogger(__name__)


class RCAEvidenceAcquirer:
    """Acquires, contracts, and bundles multi-channel evidence for RCA."""

    def __init__(
        self,
        text_retriever: Optional[TextRetriever] = None,
        visual_retriever: Optional[VisualRetriever] = None,
        allow_simulation: bool = False,
        inspector: Optional[VisualEvidenceInspector] = None
    ):
        self.text_retriever = text_retriever or TextRetriever()
        self.visual_retriever = visual_retriever or VisualRetriever(allow_simulation=allow_simulation)
        self.allow_simulation = allow_simulation
        self.inspector = inspector or get_visual_inspector()

    def parse_evidence_contract(self, query: str) -> Dict[str, Any]:
        """
        Parses query to determine asset IDs, explicitly requested documents,
        and required vs optional evidence roles.
        """
        lower_q = query.lower()

        # 1. Extract asset / equipment IDs
        raw_assets = re.findall(r"\b([A-Za-z]{1,4}-[0-9]{3,4}[A-Za-z]?)\b", query)
        assets = [a.upper() for a in raw_assets]

        # 2. Identify explicitly requested sources
        explicit_sources = []
        if any(k in lower_q for k in ["inspection report", "inspection logs", "inspection findings", "nde report"]):
            explicit_sources.append("inspection_report")
        if any(k in lower_q for k in ["sop", "standard operating procedure", "operating procedure", "maintenance sop", "manual"]):
            explicit_sources.append("maintenance_sop")
        if any(k in lower_q for k in ["vibration log", "vibration logs", "vibration trend", "vibration telemetry"]):
            explicit_sources.append("vibration_log")
        if any(k in lower_q for k in ["hazop", "risk audit", "safety audit"]):
            explicit_sources.append("hazop_audit")
        if any(k in lower_q for k in ["p&id", "pid", "piping and instrumentation", "schematic"]):
            explicit_sources.append("p_and_id")

        # 3. Determine required evidence roles
        required_roles: List[EvidenceRole] = []
        if "inspection_report" in explicit_sources or "inspection" in lower_q:
            required_roles.append(EvidenceRole.INSPECTION)
        if "maintenance_sop" in explicit_sources or any(k in lower_q for k in ["sop", "manual", "operating procedure"]):
            required_roles.append(EvidenceRole.SOP_BASELINE)
        if "vibration_log" in explicit_sources or "vibration" in lower_q:
            required_roles.append(EvidenceRole.VIBRATION)
        if "pressure" in lower_q or "overpressure" in lower_q:
            required_roles.append(EvidenceRole.PRESSURE)
        if "temperature" in lower_q or "overheat" in lower_q:
            required_roles.append(EvidenceRole.TEMPERATURE)
        if any(k in lower_q for k in ["trip", "tripped", "failed", "incident", "anomaly", "alarm"]):
            required_roles.append(EvidenceRole.INCIDENT_CHRONOLOGY)

        # 4. Optional roles
        optional_roles: List[EvidenceRole] = [
            EvidenceRole.TOPOLOGY,
            EvidenceRole.P_AND_ID,
            EvidenceRole.RISK_HAZOP,
            EvidenceRole.MAINTENANCE,
        ]

        return {
            "assets": assets,
            "explicit_sources": explicit_sources,
            "required_roles": list(set(required_roles)),
            "optional_roles": optional_roles
        }

    async def verify_asset_registration(self, workspace_id: int, asset_id: str, db: Any) -> bool:
        """
        OOD Protection: Verify that the asset exists in the plant topology,
        the simulated registry, or in workspace knowledge documents.
        """
        clean_asset = asset_id.strip().upper()
        clean_no_dash = clean_asset.replace("-", "").replace("_", "")
        if (
            clean_asset in SUPPORTED_SIMULATED_TARGETS
            or clean_no_dash in SUPPORTED_SIMULATED_TARGETS
            or resolve_equipment_alias(clean_asset) in SUPPORTED_SIMULATED_TARGETS
            or resolve_equipment_alias(clean_no_dash) in SUPPORTED_SIMULATED_TARGETS
        ):
            return True

        cursor = await db.execute(
            "SELECT id FROM graph_nodes WHERE workspace_id = ? AND (UPPER(name) = ? OR UPPER(REPLACE(name, '-', '')) = ?)",
            (workspace_id, clean_asset, clean_no_dash)
        )
        if await cursor.fetchone():
            return True

        cursor = await db.execute(
            "SELECT id FROM knowledge_sources WHERE workspace_id = ? AND (UPPER(original_filename) LIKE ? OR UPPER(name) LIKE ? OR UPPER(original_filename) LIKE ? OR UPPER(name) LIKE ?)",
            (workspace_id, f"%{clean_asset}%", f"%{clean_asset}%", f"%{clean_no_dash}%", f"%{clean_no_dash}%")
        )
        if await cursor.fetchone():
            return True

        return False

    async def acquire_evidence(
        self,
        workspace_id: int,
        query: str,
        allowed_source_ids: Optional[List[int]] = None,
        db: Optional[Any] = None,
        enable_visual: Optional[bool] = None,
        enable_topology: Optional[bool] = None,
        custom_topology_context: Optional[str] = None
    ) -> RCAEvidenceBundle:
        """
        Executes end-to-end evidence acquisition for RCA with channel observability.
        Supports explicit dependency injection (enable_visual, enable_topology, custom_topology_context)
        to prevent mutating process-global settings during ablation runs.
        """
        contract = self.parse_evidence_contract(query)
        assets = contract["assets"]
        explicit_sources = contract["explicit_sources"]
        required_roles = contract["required_roles"]
        optional_roles = contract["optional_roles"]

        channel_health = ChannelExecutionHealth(
            enabled_channels=["text"],
            attempted_channels=["text"],
            successful_channels=[],
            contributing_channels=[],
            failed_channels=[],
            requested_channels=["text", "visual", "topology"],
            executed_channels=[]
        )

        modality_coverage: Dict[str, bool] = {
            "text": False,
            "visual": False,
            "topology": False,
            "telemetry": False
        }
        telemetry_coverage: Dict[str, bool] = {}
        evidence_items: List[RCAEvidenceItem] = []
        e_counter = 1

        use_visual = enable_visual if enable_visual is not None else getattr(settings, "colpali_enabled", True)
        use_topology = enable_topology if enable_topology is not None else True

        if use_visual:
            channel_health.enabled_channels.append("visual")
            channel_health.attempted_channels.append("visual")
        if use_topology:
            channel_health.enabled_channels.append("topology")
            channel_health.attempted_channels.append("topology")

        async def _run_acquisition(conn: Any) -> RCAEvidenceBundle:
            nonlocal e_counter
            source_coverage: Dict[str, bool] = {}
            stage_latencies_ms: Dict[str, float] = {
                "asset_preflight_ms": 0.0,
                "text_search_ms": 0.0,
                "visual_maxsim_ms": 0.0,
                "visual_vlm_ms": 0.0,
                "topology_ms": 0.0,
                "total_acquisition_ms": 0.0
            }
            t_acq_start = time.perf_counter()

            # 1. OOD Asset Verification
            t_pref_0 = time.perf_counter()
            unregistered_assets = []
            for asset in assets:
                is_reg = await self.verify_asset_registration(workspace_id, asset, conn)
                if not is_reg:
                    unregistered_assets.append(asset)

            stage_latencies_ms["asset_preflight_ms"] = round((time.perf_counter() - t_pref_0) * 1000.0, 2)

            if unregistered_assets:
                logger.warning(f"RCA query referenced unregistered asset(s): {unregistered_assets}")
                channel_health.degradation_reason = f"Asset(s) {', '.join(unregistered_assets)} not registered in plant topology"
                stage_latencies_ms["total_acquisition_ms"] = round((time.perf_counter() - t_acq_start) * 1000.0, 2)
                return RCAEvidenceBundle(
                    asset_ids=unregistered_assets,
                    required_roles=required_roles,
                    optional_roles=optional_roles,
                    evidence_items=[],
                    missing_required_roles=required_roles,
                    contradictions=[],
                    source_coverage={s: False for s in explicit_sources},
                    modality_coverage=modality_coverage,
                    telemetry_coverage=telemetry_coverage,
                    retrieval_diagnostics={
                        "unregistered_assets": unregistered_assets,
                        "ood_triggered": True,
                        "stage_latencies_ms": stage_latencies_ms
                    },
                    channel_health=channel_health
                )

            # 2. Check explicit source availability in knowledge_sources
            matched_source_ids_by_req: Dict[str, List[int]] = {}
            for req_source in explicit_sources:
                search_term = req_source.replace("_", "%")
                cursor = await conn.execute(
                    "SELECT id, name, original_filename FROM knowledge_sources WHERE workspace_id = ? AND (LOWER(name) LIKE ? OR LOWER(original_filename) LIKE ?)",
                    (workspace_id, f"%{search_term}%", f"%{search_term}%")
                )
                rows = await cursor.fetchall()
                if rows:
                    source_coverage[req_source] = True
                    matched_source_ids_by_req[req_source] = [r["id"] for r in rows]
                else:
                    source_coverage[req_source] = False
                    matched_source_ids_by_req[req_source] = []

            # 3. Text Retrieval (Candidate pool: 8-10 items)
            t_text_0 = time.perf_counter()
            try:
                text_ctx, text_metas, text_ranked = await self.text_retriever.retrieve(
                    workspace_id=workspace_id,
                    query=query,
                    top_k=10,
                    allowed_source_ids=allowed_source_ids
                )
                stage_latencies_ms["text_search_ms"] = round((time.perf_counter() - t_text_0) * 1000.0, 2)
                channel_health.executed_channels.append("text")
                channel_health.successful_channels.append("text")
                channel_health.text_status = "ACTIVE"
                channel_health.text_candidate_count = len(text_ranked) if text_ranked else 0
                if text_ranked:
                    modality_coverage["text"] = True
                    for tr in text_ranked[:8]:
                        doc_text = tr.get("doc", "").strip()
                        if not doc_text:
                            continue
                        meta_item = tr.get("meta") or {}
                        filename = (
                            tr.get("filename")
                            or meta_item.get("filename")
                            or meta_item.get("document")
                            or meta_item.get("document_name")
                            or meta_item.get("original_filename")
                            or meta_item.get("name")
                        )
                        page_num = tr.get("page") or meta_item.get("page") or meta_item.get("page_number") or 1
                        sid = tr.get("source_id") or meta_item.get("source_id")

                        if not filename or filename == "Document.pdf":
                            if sid:
                                cursor_f = await conn.execute(
                                    "SELECT original_filename, name FROM knowledge_sources WHERE id = ?", (sid,)
                                )
                                s_row = await cursor_f.fetchone()
                                if s_row:
                                    filename = s_row["original_filename"] or s_row["name"] or "Document.pdf"
                                else:
                                    filename = "Document.pdf"
                            else:
                                filename = "Document.pdf"

                        # Assign role
                        role = self._classify_evidence_role(doc_text, filename)

                        # Compute confidence from raw distance
                        raw_dist = tr.get("distance")
                        if raw_dist is not None:
                            calc_conf = max(0.0, min(1.0, 1.0 - (float(raw_dist) / 0.78)))
                        else:
                            raw_score = float(tr.get("score", 0.5))
                            calc_conf = max(0.0, min(1.0, raw_score))

                        # Build native locator for text evidence without manufactured fallbacks
                        if filename.endswith((".xlsx", ".xlsm")):
                            loc = EvidenceLocator(
                                kind="spreadsheet",
                                document_type="xlsx",
                                filename=filename,
                                sheet_name=meta_item.get("sheet_name"),
                                row_start=meta_item.get("row_start"),
                                row_end=meta_item.get("row_end"),
                                col_start=meta_item.get("col_start"),
                                col_end=meta_item.get("col_end")
                            )
                        elif filename.endswith(".csv"):
                            loc = EvidenceLocator(
                                kind="row_range",
                                document_type="csv",
                                filename=filename,
                                sheet_name=meta_item.get("sheet_name"),
                                row_start=meta_item.get("row_start"),
                                row_end=meta_item.get("row_end")
                            )
                        elif filename.endswith(".docx"):
                            loc = EvidenceLocator(
                                kind="document_section",
                                document_type="docx",
                                filename=filename,
                                section_heading=meta_item.get("section_heading"),
                                page_number=int(page_num) if page_num else 1
                            )
                        else:
                            loc = EvidenceLocator(
                                kind="page",
                                document_type="pdf",
                                filename=filename,
                                page_number=int(page_num) if page_num else 1
                            )

                        evidence_items.append(
                            RCAEvidenceItem(
                                evidence_id=f"E{e_counter}",
                                source_type="pdf",
                                workspace_id=workspace_id,
                                source_id=sid,
                                filename=filename,
                                page_number=int(page_num) if page_num else 1,
                                processing_version=meta_item.get("processing_version", "v1"),
                                retrieval_channel="text",
                                evidence_role=role,
                                content=doc_text[:600],
                                confidence=calc_conf,
                                locator=loc,
                                equipment_ids=assets
                            )
                        )
                        e_counter += 1
                        if "text" not in channel_health.contributing_channels:
                            channel_health.contributing_channels.append("text")
            except Exception as te:
                logger.error(f"Text retrieval failed in RCA acquisition: {te}")
                channel_health.failed_channels.append("text")
                channel_health.text_status = "ERROR"

            # 4. Visual Retrieval (Candidate pool via ColModernVBERT / ColPali)
            if use_visual:
                t_vis_0 = time.perf_counter()
                try:
                    vis_results = await self.visual_retriever.retrieve(
                        workspace_id=workspace_id,
                        query=query,
                        top_k=5,
                        allowed_source_ids=allowed_source_ids
                    )
                    stage_latencies_ms["visual_maxsim_ms"] = round((time.perf_counter() - t_vis_0) * 1000.0, 2)
                    channel_health.visual_candidate_count = len(vis_results) if vis_results else 0
                    
                    custom_prov = getattr(self.visual_retriever, "_custom_provider", None)
                    if custom_prov and hasattr(custom_prov, "is_available"):
                        prov = custom_prov
                    else:
                        prov = get_visual_embedding_provider(allow_simulation=self.allow_simulation)

                    is_avail = False
                    if prov is not None:
                        is_avail = prov.is_available() if hasattr(prov, "is_available") else True
                    elif custom_prov:
                        is_avail = True

                    if is_avail:
                        channel_health.executed_channels.append("visual")
                        channel_health.successful_channels.append("visual")
                        channel_health.visual_status = "ACTIVE"
                        channel_health.visual_model = getattr(prov, "model_name", "Qdrant/colmodernvbert") if prov else "Custom/Simulated"
                        channel_health.visual_device = getattr(prov, "device", getattr(settings, "colpali_device", "cuda")) if prov else "cuda"
                    else:
                        channel_health.visual_status = "DISABLED"
                        channel_health.failed_channels.append("visual")
                        channel_health.degradation_reason = "Visual provider unavailable"

                    if vis_results:
                        for vr in vis_results:
                            v_role = EvidenceRole.P_AND_ID if any(k in vr.filename.lower() for k in ["p&id", "pid", "schematic", "drawing"]) else EvidenceRole.INSPECTION

                            # Inspect candidate page visually via VisualEvidenceInspector
                            insp_res = None
                            try:
                                insp_res = await self.inspector.inspect_page(
                                    workspace_id=workspace_id,
                                    source_id=vr.source_id,
                                    page_number=vr.page_number,
                                    filename=vr.filename,
                                    visual_score=float(vr.score),
                                    processing_version=vr.processing_version,
                                    query=query
                                )
                                if insp_res:
                                    stage_latencies_ms["visual_vlm_ms"] = round(stage_latencies_ms.get("visual_vlm_ms", 0.0) + insp_res.inspection_latency_ms, 2)
                                    channel_health.visual_inspector_executed = True
                            except Exception as ie:
                                logger.warning(f"Visual inspection failed on {vr.filename} page {vr.page_number}: {ie}")

                            # ONLY promote candidate to RCAEvidenceItem if visual inspection was a SUCCESS and valid observation was produced
                            if insp_res and insp_res.inspection_status == VisualInspectionStatus.SUCCESS and insp_res.vlm_succeeded and insp_res.observation_valid:
                                obs_text = insp_res.vlm_observation
                                extracted_eq = list(dict.fromkeys(assets + insp_res.equipment_tags))

                                vis_loc = EvidenceLocator(
                                    kind="page",
                                    document_type="pdf" if vr.filename.endswith(".pdf") else ("xlsx" if vr.filename.endswith((".xlsx", ".xlsm")) else "image"),
                                    filename=vr.filename,
                                    page_number=vr.page_number
                                )
                                evidence_items.append(
                                    RCAEvidenceItem(
                                        evidence_id=f"E{e_counter}",
                                        source_type="image",
                                        workspace_id=workspace_id,
                                        source_id=vr.source_id,
                                        filename=vr.filename,
                                        page_number=vr.page_number,
                                        processing_version=vr.processing_version,
                                        retrieval_channel="visual",
                                        evidence_role=v_role,
                                        content=obs_text,
                                        confidence=min(1.0, max(0.0, float(vr.score) / 10.0)),
                                        corroborated=bool(insp_res.ocr_corroborated) if (insp_res.ocr_corroborated is not None) else bool(insp_res.tag_corroboration),
                                        locator=vis_loc,
                                        equipment_ids=extracted_eq,
                                        metadata={
                                            "visual_score": float(vr.score),
                                            "corroborated_tags": insp_res.equipment_tags,
                                            "vlm_model": insp_res.vlm_model,
                                            "inspection_latency_ms": insp_res.inspection_latency_ms,
                                            "inspection_status": insp_res.inspection_status.value
                                        }
                                    )
                                )
                                e_counter += 1
                                modality_coverage["visual"] = True
                                if "visual" not in channel_health.contributing_channels:
                                    channel_health.contributing_channels.append("visual")
                            else:
                                logger.info(f"Visual candidate {vr.filename} page {vr.page_number} excluded: status {getattr(insp_res, 'inspection_status', 'FAILED')}")

                    # Role-aware acquisition guarantee: If P&ID role is requested, also check any P&ID drawings in workspace
                    if (EvidenceRole.P_AND_ID in required_roles or "p_and_id" in explicit_sources):
                        already_have_pid = any(item.evidence_role == EvidenceRole.P_AND_ID and item.retrieval_channel == "visual" for item in evidence_items)
                        if not already_have_pid:
                            pid_query = """SELECT id, name, original_filename FROM knowledge_sources 
                                           WHERE workspace_id = ? AND processing_status = 'completed'
                                             AND (LOWER(name) LIKE '%p&id%' OR LOWER(original_filename) LIKE '%p&id%' OR LOWER(name) LIKE '%pid%' OR LOWER(original_filename) LIKE '%pid%')"""
                            cursor_pid = await conn.execute(pid_query, (workspace_id,))
                            pid_rows = await cursor_pid.fetchall()
                            for prow in pid_rows:
                                if allowed_source_ids and prow["id"] not in allowed_source_ids:
                                    continue
                                pid_fn = prow["original_filename"] or prow["name"]
                                try:
                                    insp_pid = await self.inspector.inspect_page(
                                        workspace_id=workspace_id,
                                        source_id=prow["id"],
                                        page_number=1,
                                        filename=pid_fn,
                                        visual_score=25.0,
                                        query=query
                                    )
                                    if insp_pid:
                                        channel_health.visual_inspector_executed = True
                                        channel_health.visual_candidate_count = max(channel_health.visual_candidate_count, 1)
                                    if insp_pid and insp_pid.inspection_status == VisualInspectionStatus.SUCCESS and insp_pid.vlm_succeeded and insp_pid.observation_valid:
                                        vis_loc = EvidenceLocator(kind="page", document_type="pdf", filename=pid_fn, page_number=1)
                                        evidence_items.append(
                                            RCAEvidenceItem(
                                                evidence_id=f"E{e_counter}",
                                                source_type="image",
                                                workspace_id=workspace_id,
                                                source_id=prow["id"],
                                                filename=pid_fn,
                                                page_number=1,
                                                processing_version="v1",
                                                retrieval_channel="visual",
                                                evidence_role=EvidenceRole.P_AND_ID,
                                                content=insp_pid.vlm_observation,
                                                confidence=0.9,
                                                corroborated=bool(insp_pid.ocr_corroborated) if (insp_pid.ocr_corroborated is not None) else bool(insp_pid.tag_corroboration),
                                                locator=vis_loc,
                                                equipment_ids=list(dict.fromkeys(assets + insp_pid.equipment_tags)),
                                                metadata={
                                                    "visual_score": 25.0,
                                                    "corroborated_tags": insp_pid.equipment_tags,
                                                    "vlm_model": insp_pid.vlm_model,
                                                    "inspection_latency_ms": insp_pid.inspection_latency_ms,
                                                    "inspection_status": insp_pid.inspection_status.value
                                                }
                                            )
                                        )
                                        e_counter += 1
                                        modality_coverage["visual"] = True
                                        if "visual" not in channel_health.contributing_channels:
                                            channel_health.contributing_channels.append("visual")
                                        break
                                except Exception as e_pid:
                                    logger.warning(f"Failed fallback P&ID visual inspection: {e_pid}")
                except Exception as ve:
                    logger.warning(f"Visual retrieval failed in RCA acquisition: {ve}")
                    channel_health.failed_channels.append("visual")
                    channel_health.visual_status = "ERROR"
            else:
                channel_health.visual_status = "DISABLED"
                channel_health.degradation_reason = "Visual channel disabled for condition"

            # 5. Plant Topology Graph Retrieval (max_hops = 2)
            if use_topology:
                t_topo_0 = time.perf_counter()
                try:
                    if custom_topology_context is not None:
                        topo_ctx = custom_topology_context
                    else:
                        topo_ctx = await query_graph_context(workspace_id, query, max_hops=2)

                    stage_latencies_ms["topology_ms"] = round((time.perf_counter() - t_topo_0) * 1000.0, 2)
                    cur_n = await conn.execute("SELECT COUNT(*) as c FROM graph_nodes WHERE workspace_id = ?", (workspace_id,))
                    n_row = await cur_n.fetchone()
                    channel_health.topology_node_count = n_row["c"] if n_row else 0
                    cur_e = await conn.execute("SELECT COUNT(*) as c FROM graph_edges WHERE workspace_id = ?", (workspace_id,))
                    e_row = await cur_e.fetchone()
                    channel_health.topology_edge_count = e_row["c"] if e_row else 0

                    if topo_ctx and topo_ctx.strip():
                        channel_health.executed_channels.append("topology")
                        channel_health.successful_channels.append("topology")
                        channel_health.topology_status = "ACTIVE"
                        modality_coverage["topology"] = True
                        evidence_items.append(
                            RCAEvidenceItem(
                                evidence_id=f"E{e_counter}",
                                source_type="topology",
                                workspace_id=workspace_id,
                                filename="Plant_Topology_Graph",
                                page_number=None,
                                retrieval_channel="topology",
                                evidence_role=EvidenceRole.TOPOLOGY,
                                content=topo_ctx.strip(),
                                confidence=1.0,
                                locator=EvidenceLocator(kind="topology_node", document_type="topology", filename="Plant_Topology_Graph", raw_locator="Graph Context"),
                                equipment_ids=assets
                            )
                        )
                        e_counter += 1
                        if "topology" not in channel_health.contributing_channels:
                            channel_health.contributing_channels.append("topology")
                    else:
                        channel_health.topology_status = "EMPTY"
                except Exception as ge:
                    logger.warning(f"Topology query failed in RCA acquisition: {ge}")
                    channel_health.failed_channels.append("topology")
                    channel_health.topology_status = "ERROR"
            else:
                channel_health.topology_status = "DISABLED"

            # 6. Evaluate requested source coverage
            source_coverage = {}
            for req_src in explicit_sources:
                found = False
                for item in evidence_items:
                    fn_lower = item.filename.lower()
                    if req_src == "inspection_report" and any(k in fn_lower for k in ["inspection", "nde", "ndt"]):
                        found = True
                        break
                    elif req_src == "maintenance_sop" and any(k in fn_lower for k in ["sop", "procedure", "maintenance", "manual"]):
                        found = True
                        break
                    elif req_src == "vibration_log" and any(k in fn_lower for k in ["vibration", "spectral", "fft", "telemetry"]):
                        found = True
                        break
                    elif req_src == "hazop_audit" and any(k in fn_lower for k in ["hazop", "risk"]):
                        found = True
                        break
                    elif req_src == "p_and_id" and any(k in fn_lower for k in ["p&id", "pid", "schematic"]):
                        found = True
                        break
                source_coverage[req_src] = found

            # 7. Final evidence channels & channel counts
            final_channels = set()
            channel_counts = {}
            for item in evidence_items:
                ch = item.retrieval_channel.upper()
                final_channels.add(ch)
                channel_counts[ch] = channel_counts.get(ch, 0) + 1

            # 8. Check required roles satisfaction
            found_roles = {item.evidence_role for item in evidence_items}
            missing_roles = [r for r in required_roles if r not in found_roles]

            # 9. Check channel degradation
            if getattr(settings, "hybrid_retrieval_enabled", True) and "visual" not in channel_health.executed_channels:
                channel_health.hybrid_status = "DEGRADED"
                if not channel_health.degradation_reason:
                    channel_health.degradation_reason = "visual retrieval unavailable; using text + topology only"
                logger.info(f"HYBRID_RAG_DEGRADED: {channel_health.degradation_reason}")

            stage_latencies_ms["total_acquisition_ms"] = round((time.perf_counter() - t_acq_start) * 1000.0, 2)

            return RCAEvidenceBundle(
                asset_ids=assets,
                required_roles=required_roles,
                optional_roles=optional_roles,
                evidence_items=evidence_items,
                missing_required_roles=missing_roles,
                contradictions=[],
                source_coverage=source_coverage,
                modality_coverage=modality_coverage,
                telemetry_coverage=telemetry_coverage,
                final_evidence_channels=sorted(final_channels),
                evidence_channel_counts=channel_counts,
                stage_latencies_ms=stage_latencies_ms,
                retrieval_diagnostics={
                    "total_items": len(evidence_items),
                    "assets": assets,
                    "explicit_sources": explicit_sources,
                    "stage_latencies_ms": stage_latencies_ms
                },
                channel_health=channel_health
            )

        if db is not None:
            return await _run_acquisition(db)
        async with get_db() as conn:
            return await _run_acquisition(conn)

    def _classify_evidence_role(self, text: str, filename: str) -> EvidenceRole:
        """Classifies evidence into canonical EvidenceRole based on text content and filename."""
        fn_lower = filename.lower()
        t_lower = text.lower()

        if any(k in fn_lower for k in ["p&id", "pid", "schematic", "drawing"]):
            return EvidenceRole.P_AND_ID
        if any(k in fn_lower for k in ["inspection", "nde", "ndt", "metallurgical"]):
            return EvidenceRole.INSPECTION
        if any(k in fn_lower for k in ["sop", "procedure", "operating_manual", "api610", "standard"]):
            return EvidenceRole.SOP_BASELINE
        if any(k in fn_lower for k in ["maintenance", "actuator_log", "work_order", "repair"]):
            return EvidenceRole.MAINTENANCE
        if any(k in fn_lower for k in ["vibration", "telemetry", "scada", "trend"]):
            return EvidenceRole.VIBRATION
        if any(k in fn_lower for k in ["chrono", "incident", "trip_report", "event_log"]):
            return EvidenceRole.INCIDENT_CHRONOLOGY

        # Content fallback
        if any(w in t_lower for w in ["vibration", "overall vibration", "1x", "2x", "subsynchronous"]):
            return EvidenceRole.VIBRATION
        if any(w in t_lower for w in ["journal bearing", "bearing temperature", "thrust bearing"]):
            return EvidenceRole.TEMPERATURE
        if any(w in t_lower for w in ["discharge pressure", "suction pressure", "differential pressure"]):
            return EvidenceRole.PRESSURE
        if any(w in t_lower for w in ["visual inspection", "ultrasonic", "dye penetrant", "corrosion pitting"]):
            return EvidenceRole.INSPECTION
        if any(w in t_lower for w in ["procedure", "step 1", "pre-start check", "operating limit"]):
            return EvidenceRole.SOP_BASELINE
        if any(w in t_lower for w in ["actuator stroke", "greased stem", "repacked gland"]):
            return EvidenceRole.MAINTENANCE

        return EvidenceRole.INCIDENT_CHRONOLOGY


async def validate_full_multimodal_runtime(
    workspace_id: int = 9998,
    source_id: int = 1075,
    sample_query: str = "FV-302 control valve upstream of reactor R-301"
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Authoritative 9-point fail-closed preflight check of the full multimodal visual runtime.
    Validates:
    1. settings.colpali_enabled == True
    2. settings.enable_multimodal_vision == True
    3. ONNX / model files exist on disk
    4. ColPaliLocalProvider constructed
    5. Query embedding computation succeeds and returns non-empty array
    6. PDF page rendering succeeds (pymupdf)
    7. Page embeddings exist on disk or compute without error
    8. Late-interaction MaxSim similarity scoring succeeds (> 0)
    9. Local VLM model is reachable in Ollama
    """
    import os
    import numpy as np
    import httpx
    import pymupdf

    cuda_dirs = [
        Path(r"C:\Program Files\NVIDIA\CUDNN\v9.22\bin\12.9\x64"),
        Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin"),
    ]
    for cd in cuda_dirs:
        if cd.exists():
            try:
                os.add_dll_directory(str(cd))
            except Exception:
                pass
            if str(cd) not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{str(cd)};{os.environ.get('PATH', '')}"

    from cognishift.core.visual_rag.embedding_provider import ColPaliLocalProvider
    from cognishift.core.document_processing.pdf_extractor import render_page_to_png_bytes
    from cognishift.core.visual_rag.vector_store import compute_maxsim

    diag: Dict[str, Any] = {}

    # Point 1: configuration enabled
    if not getattr(settings, "colpali_enabled", False):
        return False, "Preflight Point 1 Failed: settings.colpali_enabled is False", diag
    diag["point_1_colpali_enabled"] = True

    # Point 2: multimodal vision enabled
    if not getattr(settings, "enable_multimodal_vision", False):
        return False, "Preflight Point 2 Failed: settings.enable_multimodal_vision is False", diag
    diag["point_2_multimodal_vision_enabled"] = True

    # Point 3: weights/onnx exist on disk
    model_path = Path(settings.colpali_model_path)
    if not model_path.is_absolute():
        model_path = settings.project_root / model_path
    cache_dirs = [
        model_path,
        settings.project_root / "data" / "models" / "colpali",
        settings.project_root / "data" / "models" / "fastembed",
        settings.project_root / "data" / "models",
    ]
    onnx_found = any(
        (cd.exists() and ((cd / "models--Qdrant--colmodernvbert").exists() or (cd / "model.onnx").exists()))
        for cd in cache_dirs
    )
    if not onnx_found:
        return False, f"Preflight Point 3 Failed: ONNX model weights not found in candidate paths {cache_dirs}", diag
    diag["point_3_weights_exist"] = True

    # Point 4: provider constructed
    try:
        provider = ColPaliLocalProvider(device=settings.colpali_device)
    except Exception as exc:
        return False, f"Preflight Point 4 Failed: ColPaliLocalProvider construction failed: {exc}", diag
    diag["point_4_provider_constructed"] = True
    diag["provider_device"] = getattr(provider, "device", "unknown")

    # Point 5: query embedding works
    try:
        q_emb = provider.embed_query(sample_query)
        if q_emb is None or len(q_emb) == 0:
            return False, "Preflight Point 5 Failed: query embedding returned empty array", diag
    except Exception as exc:
        return False, f"Preflight Point 5 Failed: query embedding threw exception: {exc}", diag
    diag["point_5_query_embed_shape"] = list(q_emb.shape)

    # Point 6: page rendering works
    pdf_path: Optional[Path] = None
    try:
        async with get_db() as db:
            cur = await db.execute("SELECT local_path, original_filename FROM knowledge_sources WHERE id = ? AND workspace_id = ?", (source_id, workspace_id))
            row = await cur.fetchone()
            if row and row["local_path"]:
                cand = Path(row["local_path"])
                if cand.exists():
                    pdf_path = cand
    except Exception:
        pass
    if not pdf_path:
        fallback = settings.project_root / "data" / "benchmark_v2" / "corpus" / "RCA-CASE-A-DOC2_Feed_Control_FV302_Spatial_PID.pdf"
        if fallback.exists():
            pdf_path = fallback
    if not pdf_path or not pdf_path.exists():
        return False, f"Preflight Point 6 Failed: Source {source_id} PDF not found on disk", diag

    try:
        doc = pymupdf.open(pdf_path)
        page_png = render_page_to_png_bytes(doc, 1, 150)
        doc.close()
        if not page_png:
            return False, "Preflight Point 6 Failed: render_page_to_png_bytes returned empty bytes", diag
    except Exception as exc:
        return False, f"Preflight Point 6 Failed: PDF rendering failed: {exc}", diag
    diag["point_6_page_png_bytes"] = len(page_png)

    # Point 7: page embeddings exist on disk or compute without error
    page_emb: Optional[np.ndarray] = None
    ws_vec_dir = settings.project_root / "data" / "workspaces" / str(workspace_id) / "visual_vectors"
    cand_files = list(ws_vec_dir.glob(f"source_{source_id}_*/page_1.npy")) if ws_vec_dir.exists() else []
    if cand_files and cand_files[0].exists():
        try:
            page_emb = np.load(cand_files[0])
            diag["point_7_source"] = "disk_cache"
        except Exception:
            page_emb = None
    if page_emb is None:
        try:
            page_emb = provider.embed_page(page_png)
            diag["point_7_source"] = "live_computed"
        except Exception as exc:
            return False, f"Preflight Point 7 Failed: page embedding compute failed: {exc}", diag
    diag["point_7_page_embed_shape"] = list(page_emb.shape)

    # Point 8: similarity scoring works
    try:
        maxsim_score = compute_maxsim(q_emb, page_emb)
        if maxsim_score <= 0.0 or np.isnan(maxsim_score):
            return False, f"Preflight Point 8 Failed: MaxSim similarity score non-positive ({maxsim_score})", diag
    except Exception as exc:
        return False, f"Preflight Point 8 Failed: MaxSim scoring exception: {exc}", diag
    diag["point_8_maxsim_score"] = float(maxsim_score)

    # Point 9: local VLM model available in Ollama
    vlm_model = getattr(settings, "vision_model", "moondream")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code != 200:
                return False, f"Preflight Point 9 Failed: Ollama API returned status {resp.status_code}", diag
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            vlm_name_prefix = vlm_model.split(":")[0]
            is_present = any(vlm_name_prefix in m for m in models)
            if not is_present:
                return False, f"Preflight Point 9 Failed: Vision model '{vlm_model}' not found in local Ollama tags: {models}", diag
    except Exception as exc:
        return False, f"Preflight Point 9 Failed: Ollama connection failed: {exc}", diag
    diag["point_9_vlm_available"] = True
    diag["vlm_model"] = vlm_model

    return True, "All 9 visual runtime preflight checks passed successfully", diag

