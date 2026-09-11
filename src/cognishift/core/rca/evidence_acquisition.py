"""RCA Evidence Acquisition Subsystem.

Implements role-aware, multi-channel evidence retrieval across Text RAG, Visual ColPali,
Plant Topology Graph, and verified Telemetry. Enforces explicit evidence contracts
and prevents silent substitution of missing documents or nonexistent assets.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.core.rca.schemas import (
    EvidenceRole,
    RCAEvidenceItem,
    RCAEvidenceBundle,
    ChannelExecutionHealth
)
from cognishift.core.tool_schemas import SUPPORTED_SIMULATED_TARGETS, resolve_equipment_alias
from cognishift.core.retrieval.text_retriever import TextRetriever
from cognishift.core.retrieval.visual_retriever import VisualRetriever
from cognishift.core.retrieval.evidence_fusion import EvidenceFusion
from cognishift.core.graph_memory import query_graph_context
from cognishift.core.retrieval.visual_inspector import VisualEvidenceInspector, get_visual_inspector

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
        # Check canonical simulated registry
        if (
            clean_asset in SUPPORTED_SIMULATED_TARGETS
            or clean_no_dash in SUPPORTED_SIMULATED_TARGETS
            or resolve_equipment_alias(clean_asset) in SUPPORTED_SIMULATED_TARGETS
            or resolve_equipment_alias(clean_no_dash) in SUPPORTED_SIMULATED_TARGETS
        ):
            return True

        # Check workspace graph nodes
        cursor = await db.execute(
            "SELECT id FROM graph_nodes WHERE workspace_id = ? AND (UPPER(name) = ? OR UPPER(REPLACE(name, '-', '')) = ?)",
            (workspace_id, clean_asset, clean_no_dash)
        )
        if await cursor.fetchone():
            return True

        # Check knowledge sources in workspace
        cursor = await db.execute(
            """SELECT id FROM knowledge_sources 
               WHERE workspace_id = ? AND (
                   UPPER(name) LIKE ? OR UPPER(original_filename) LIKE ?
                   OR UPPER(name) LIKE ? OR UPPER(original_filename) LIKE ?
               )""",
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
        db: Optional[Any] = None
    ) -> RCAEvidenceBundle:
        """
        Executes end-to-end evidence acquisition for RCA with channel observability.
        """
        contract = self.parse_evidence_contract(query)
        assets = contract["assets"]
        explicit_sources = contract["explicit_sources"]
        required_roles = contract["required_roles"]
        optional_roles = contract["optional_roles"]

        channel_health = ChannelExecutionHealth(
            requested_channels=["text", "visual", "topology"],
            executed_channels=[],
            failed_channels=[]
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

        async def _run_acquisition(conn: Any) -> RCAEvidenceBundle:
            nonlocal e_counter
            source_coverage: Dict[str, bool] = {}

            # 1. OOD Asset Verification
            unregistered_assets = []
            for asset in assets:
                is_reg = await self.verify_asset_registration(workspace_id, asset, conn)
                if not is_reg:
                    unregistered_assets.append(asset)

            # If an unregistered asset was explicitly queried (e.g. K-888, P-000)
            if unregistered_assets:
                logger.warning(f"RCA query referenced unregistered asset(s): {unregistered_assets}")
                channel_health.degradation_reason = f"Asset(s) {', '.join(unregistered_assets)} not registered in plant topology"
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
                    retrieval_diagnostics={"unregistered_assets": unregistered_assets, "ood_triggered": True},
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
            try:
                text_ctx, text_metas, text_ranked = await self.text_retriever.retrieve(
                    workspace_id=workspace_id,
                    query=query,
                    top_k=10,
                    allowed_source_ids=allowed_source_ids
                )
                channel_health.executed_channels.append("text")
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

                        # Compute confidence from raw distance (monotonic: distance 0.0 -> 1.0, distance 0.78 -> 0.0)
                        raw_dist = tr.get("distance")
                        if raw_dist is not None:
                            calc_conf = max(0.0, min(1.0, 1.0 - (float(raw_dist) / 0.78)))
                        else:
                            raw_score = float(tr.get("score", 0.5))
                            calc_conf = max(0.0, min(1.0, raw_score))

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
                                equipment_ids=assets
                            )
                        )
                        e_counter += 1
            except Exception as te:
                logger.error(f"Text retrieval failed in RCA acquisition: {te}")
                channel_health.failed_channels.append("text")
                channel_health.text_status = "ERROR"

            # 4. Visual Retrieval (Candidate pool: 5 items via ColPali / ColModernVBERT)
            try:
                vis_results = await self.visual_retriever.retrieve(
                    workspace_id=workspace_id,
                    query=query,
                    top_k=5,
                    allowed_source_ids=allowed_source_ids
                )
                channel_health.visual_candidate_count = len(vis_results) if vis_results else 0
                if self.visual_retriever._custom_provider or getattr(settings, "colpali_enabled", True):
                    channel_health.executed_channels.append("visual")
                    channel_health.visual_status = "ACTIVE"
                    channel_health.visual_model = getattr(settings, "colpali_model_name", "vidore/colmodernvbert")
                    channel_health.visual_device = getattr(settings, "colpali_device", "cuda")
                else:
                    channel_health.visual_status = "DISABLED"
                    channel_health.degradation_reason = "ColPali disabled in system settings"

                if vis_results:
                    modality_coverage["visual"] = True
                    for vr in vis_results:
                        # Avoid duplicate page if already captured by text with same coordinates
                        existing = next(
                            (e for e in evidence_items if e.filename == vr.filename and e.page_number == vr.page_number),
                            None
                        )
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
                        except Exception as ie:
                            logger.warning(f"Visual inspection failed on {vr.filename} page {vr.page_number}: {ie}")

                        obs_text = insp_res.vlm_observation if (insp_res and insp_res.vlm_observation) else f"Visual page match ({vr.filename} Page {vr.page_number}) with MaxSim relevance score {vr.score:.2f}."
                        extracted_eq = list(dict.fromkeys(assets + (insp_res.equipment_tags if insp_res else [])))

                        if existing:
                            existing.retrieval_channel = "hybrid"
                            existing.confidence = max(existing.confidence, min(1.0, float(vr.score) / 10.0))
                            if insp_res and insp_res.vlm_observation and "Visual match" not in insp_res.vlm_observation:
                                existing.content += f"\n[Visual Corroboration]: {insp_res.vlm_observation}"
                            for eq in extracted_eq:
                                if eq not in existing.equipment_ids:
                                    existing.equipment_ids.append(eq)
                            continue

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
                                equipment_ids=extracted_eq
                            )
                        )
                        e_counter += 1
            except Exception as ve:
                logger.warning(f"Visual retrieval failed in RCA acquisition: {ve}")
                channel_health.failed_channels.append("visual")
                channel_health.visual_status = "ERROR"

            # 5. Plant Topology Graph Retrieval (max_hops = 2)
            try:
                topo_ctx = await query_graph_context(workspace_id, query, max_hops=2)
                cur_n = await conn.execute("SELECT COUNT(*) as c FROM graph_nodes WHERE workspace_id = ?", (workspace_id,))
                n_row = await cur_n.fetchone()
                channel_health.topology_node_count = n_row["c"] if n_row else 0
                cur_e = await conn.execute("SELECT COUNT(*) as c FROM graph_edges WHERE workspace_id = ?", (workspace_id,))
                e_row = await cur_e.fetchone()
                channel_health.topology_edge_count = e_row["c"] if e_row else 0

                if topo_ctx and topo_ctx.strip():
                    channel_health.executed_channels.append("topology")
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
                            equipment_ids=assets
                        )
                    )
                    e_counter += 1
                else:
                    channel_health.topology_status = "EMPTY"
            except Exception as ge:
                logger.warning(f"Topology query failed in RCA acquisition: {ge}")
                channel_health.failed_channels.append("topology")
                channel_health.topology_status = "ERROR"

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
                retrieval_diagnostics={
                    "total_items": len(evidence_items),
                    "assets": assets,
                    "explicit_sources": explicit_sources,
                    "missing_explicit_sources": [s for s, f in source_coverage.items() if not f],
                    "text_candidate_count": channel_health.text_candidate_count,
                    "visual_candidate_count": channel_health.visual_candidate_count,
                    "topology_node_count": channel_health.topology_node_count,
                    "topology_edge_count": channel_health.topology_edge_count
                },
                channel_health=channel_health
            )

        if db is not None:
            return await _run_acquisition(db)
        async with get_db() as conn:
            return await _run_acquisition(conn)

    def _classify_evidence_role(self, content: str, filename: str) -> EvidenceRole:
        """Heuristically tags an evidence item with its specific engineering role."""
        lower = (content + " " + filename).lower()
        if any(k in lower for k in ["p&id", "pid", "flow diagram", "schematic", "piping"]):
            return EvidenceRole.P_AND_ID
        if any(k in lower for k in ["vibration log", "vibration trend", "mm/s", "radial probe", "spectral"]):
            return EvidenceRole.VIBRATION
        if any(k in lower for k in ["sop", "operating procedure", "threshold", "trip limit", "normal operating"]):
            return EvidenceRole.SOP_BASELINE
        if any(k in lower for k in ["inspection report", "visual inspection", "crack", "wear", "wall thickness", "nde", "ndt"]):
            return EvidenceRole.INSPECTION
        if any(k in lower for k in ["overpressure", "pressure spike", "bar(g)", "psi", "relief valve"]):
            return EvidenceRole.PRESSURE
        if any(k in lower for k in ["bearing temperature", "thermocouple", "overheat", "°c"]):
            return EvidenceRole.TEMPERATURE
        if any(k in lower for k in ["hazop", "risk assessment", "safeguard", "consequence"]):
            return EvidenceRole.RISK_HAZOP
        if any(k in lower for k in ["maintenance log", "work order", "overhaul", "replaced"]):
            return EvidenceRole.MAINTENANCE
        if any(k in lower for k in ["chronology", "sequence of events", "trip sequence", "breaker tripped"]):
            return EvidenceRole.INCIDENT_CHRONOLOGY
        return EvidenceRole.OTHER
