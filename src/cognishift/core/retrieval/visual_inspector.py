"""
Visual Evidence Inspector for CogniShift.
Executes targeted on-demand visual page inspection via local VLM (e.g. Moondream, Qwen2.5-VL)
and corroborates visual observations with deterministic OCR verifier.
Shared across HybridDocumentRetriever and RCAEvidenceAcquirer.
"""
import time
import json
import asyncio
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.core.rca.schemas import ObservationQualityStatus
from cognishift.core.visual_rag.schemas import CorroborationResult
from cognishift.core.visual_rag.page_cache import render_page_image_on_demand
from cognishift.core.visual_rag.page_verifier import DeterministicPageVerifier, get_page_verifier
from cognishift.core.document_processing.vision_service import VisionProcessingService
from cognishift.core.document_processing.schemas import VisionRequirement

logger = logging.getLogger(__name__)

TAG_RE = re.compile(r"\b([A-Za-z]{1,4}-\d{2,4}[A-Za-z]?)\b")


class VisualInspectionStatus(str, Enum):
    VERIFIED = "VERIFIED"
    OBSERVED_UNCORROBORATED = "OBSERVED_UNCORROBORATED"
    SUCCESS = "SUCCESS"
    RASTERIZATION_FAILED = "RASTERIZATION_FAILED"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    VLM_FAILED = "VLM_FAILED"
    NO_OBSERVATION = "NO_OBSERVATION"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    DEGRADED = "DEGRADED"


class VisualInspectionResult(BaseModel):
    """Result of targeted visual evidence inspection on a page or sheet tile."""
    workspace_id: int
    source_id: int
    filename: str
    page_number: int
    processing_version: str = "v1"
    visual_score: float = 0.0
    inspection_status: VisualInspectionStatus = VisualInspectionStatus.DEGRADED
    rasterized: bool = False
    vlm_executed: bool = False
    vlm_succeeded: bool = False
    observation_valid: bool = False
    verification_executed: bool = False
    tag_corroboration: Optional[bool] = None
    numeric_corroboration: Optional[bool] = None
    visual_relation_observation: Optional[str] = None
    vlm_observation: str = ""
    corroboration_results: List[CorroborationResult] = Field(default_factory=list)
    ocr_corroborated: Optional[bool] = None
    equipment_tags: List[str] = Field(default_factory=list)
    instrument_tags: List[str] = Field(default_factory=list)
    validated_numeric_claims: List[Dict[str, Any]] = Field(default_factory=list)
    locator: str = ""
    inspection_latency_ms: float = 0.0
    vlm_model: str = ""
    quality_status: ObservationQualityStatus = ObservationQualityStatus.OBSERVED_UNCORROBORATED
    observed_relations: List[Dict[str, Any]] = Field(default_factory=list)


class VisualEvidenceInspector:
    """
    On-demand visual evidence inspector.
    Renders the candidate page image, queries the local VLM with targeted prompts,
    and corroborates observed equipment tags, valves, and readings via deterministic OCR.
    """

    def __init__(
        self,
        vision_service: Optional[VisionProcessingService] = None,
        verifier: Optional[DeterministicPageVerifier] = None
    ):
        self.vision_service = vision_service or VisionProcessingService()
        self.verifier = verifier or get_page_verifier()
        self._source_path_cache: Dict[int, Optional[Path]] = {}

    async def _resolve_file_path(self, source_id: int) -> Optional[Path]:
        if source_id in self._source_path_cache:
            return self._source_path_cache[source_id]

        try:
            async with get_db() as db:
                cursor = await db.execute(
                    "SELECT local_path FROM knowledge_sources WHERE id = ?", (source_id,)
                )
                row = await cursor.fetchone()
                p = Path(row["local_path"]) if row and row["local_path"] else None
                self._source_path_cache[source_id] = p
                return p
        except Exception as e:
            logger.warning(f"Failed resolving file path for source {source_id}: {e}")
            return None

    async def inspect_page(
        self,
        workspace_id: int,
        source_id: int,
        page_number: int,
        filename: str = "",
        visual_score: float = 0.0,
        processing_version: str = "v1",
        query: str = "",
        prompt_override: Optional[str] = None
    ) -> VisualInspectionResult:
        """
        Inspects a specific document page or tile visually.
        """
        # Dynamically resolve active_processing_version if "v1" or empty
        if (not processing_version or processing_version == "v1") and source_id:
            try:
                async with get_db() as db:
                    cur = await db.execute(
                        "SELECT active_processing_version FROM knowledge_sources WHERE id = ?", (source_id,)
                    )
                    row = await cur.fetchone()
                    if row and row["active_processing_version"]:
                        processing_version = row["active_processing_version"]
            except Exception as e:
                logger.warning(f"Could not resolve active_processing_version for source {source_id}: {e}")

        locator = f"Page {page_number}"
        file_path = await self._resolve_file_path(source_id)

        if not file_path or not file_path.exists():
            return VisualInspectionResult(
                workspace_id=workspace_id,
                source_id=source_id,
                filename=filename or "document.pdf",
                page_number=page_number,
                processing_version=processing_version,
                visual_score=visual_score,
                inspection_status=VisualInspectionStatus.SOURCE_NOT_FOUND,
                quality_status=ObservationQualityStatus.SOURCE_NOT_FOUND,
                rasterized=False,
                vlm_executed=False,
                vlm_succeeded=False,
                observation_valid=False,
                vlm_observation=f"Document source file not found on disk ({filename} {locator}) with score {visual_score:.2f}.",
                locator=locator
            )

        suffix = file_path.suffix.lower()
        image_bytes: Optional[bytes] = None

        try:
            if suffix == ".pdf":
                dpi = getattr(settings, "colpali_raster_dpi", 150)
                image_bytes = await render_page_image_on_demand(file_path, page_number, dpi=dpi)
            elif suffix in [".png", ".jpg", ".jpeg"]:
                image_bytes = await asyncio.to_thread(file_path.read_bytes)
            elif suffix in [".xlsx", ".xlsm"]:
                # XLSX visual tile rendering fallback if available
                locator = f"Sheet Tile | Page {page_number}"
                try:
                    from cognishift.core.document_processing.office_renderer import render_xlsx_tile_bytes
                    image_bytes = await render_xlsx_tile_bytes(file_path, tile_index=page_number - 1)
                except Exception:
                    pass
        except Exception as re_err:
            logger.warning(f"Error rasterizing {filename} page {page_number}: {re_err}")

        if not image_bytes:
            return VisualInspectionResult(
                workspace_id=workspace_id,
                source_id=source_id,
                filename=filename,
                page_number=page_number,
                processing_version=processing_version,
                visual_score=visual_score,
                inspection_status=VisualInspectionStatus.RASTERIZATION_FAILED,
                quality_status=ObservationQualityStatus.RASTERIZATION_FAILED,
                rasterized=False,
                vlm_executed=False,
                vlm_succeeded=False,
                observation_valid=False,
                vlm_observation=f"Rasterization unavailable for {filename} {locator}.",
                locator=locator
            )

        t_insp_0 = time.perf_counter()
        target_prompt = prompt_override or (
            "Describe the visible equipment and instrument tags, physical piping connections, "
            "and flow directions between components in this engineering diagram. "
            "Specify which valves or instruments are upstream, connected to, or downstream of vessels along process lines."
        )

        vlm_text = ""
        corroborations: List[CorroborationResult] = []
        is_corroborated: Optional[bool] = None
        tag_corroborated: Optional[bool] = None
        numeric_corroborated: Optional[bool] = None
        extracted_tags: List[str] = []
        observed_relations: List[Dict[str, Any]] = []
        vlm_succeeded = False
        vlm_failed = False
        verification_executed = False

        try:
            v_obs = await self.vision_service.analyze_document_image(
                image_bytes=image_bytes,
                page_number=page_number,
                prompt=target_prompt,
                requirement=VisionRequirement.OPTIONAL
            )
            if v_obs and v_obs.description and v_obs.description.strip():
                vlm_text = v_obs.description.strip()
                vlm_succeeded = True

                # Parse structured JSON output from VLM if available
                parsed_json = None
                try:
                    match = re.search(r"(\{.*\})", vlm_text, re.DOTALL)
                    if match:
                        parsed_json = json.loads(match.group(1))
                    else:
                        parsed_json = json.loads(vlm_text)
                except Exception:
                    parsed_json = None

                if isinstance(parsed_json, dict):
                    for tag in parsed_json.get("observed_equipment_tags", parsed_json.get("equipment_tags", [])):
                        if isinstance(tag, str) and tag.strip():
                            extracted_tags.append(tag.strip().upper())
                    for tag in parsed_json.get("observed_instrument_tags", parsed_json.get("instrument_tags", [])):
                        if isinstance(tag, str) and tag.strip():
                            extracted_tags.append(tag.strip().upper())
                    raw_rels = parsed_json.get("observed_relations", parsed_json.get("relations", []))
                    if isinstance(raw_rels, list):
                        for rel in raw_rels:
                            if isinstance(rel, dict) and "subject" in rel and "object" in rel:
                                observed_relations.append({
                                    "subject": str(rel["subject"]).strip().upper(),
                                    "relation_type": str(rel.get("relation_type", "CONNECTED_TO")).strip().upper(),
                                    "object": str(rel["object"]).strip().upper()
                                })

                # Also regex extract tags from prose if any
                for m in TAG_RE.finditer(vlm_text):
                    extracted_tags.append(m.group(1).upper())
                extracted_tags = list(dict.fromkeys(extracted_tags))

                # Extract spatial relations from observation text ONLY (never manufacture from query)
                if not observed_relations and len(extracted_tags) >= 2:
                    v_lower = vlm_text.lower()
                    valves = [t for t in extracted_tags if t.startswith(("FV", "PV", "XV", "HV", "FCV", "PCV"))]
                    equipment = [t for t in extracted_tags if t.startswith(("R-", "K-", "P-", "C-", "T-", "V-", "E-", "HEX-"))]
                    for v in valves:
                        for eq in equipment:
                            if "upstream" in v_lower:
                                observed_relations.append({
                                    "subject": v,
                                    "relation_type": "UPSTREAM_OF",
                                    "object": eq
                                })
                            elif "downstream" in v_lower:
                                observed_relations.append({
                                    "subject": v,
                                    "relation_type": "DOWNSTREAM_OF",
                                    "object": eq
                                })
                            elif any(k in v_lower for k in ["connected", "connect", "feed", "pipe"]):
                                observed_relations.append({
                                    "subject": v,
                                    "relation_type": "CONNECTED_TO",
                                    "object": eq
                                })

                # Deterministic OCR corroboration
                if getattr(settings, "visual_verification_enabled", True):
                    verification_executed = True
                    corroborations = await self.verifier.verify_page_claims(
                        workspace_id=workspace_id,
                        source_id=source_id,
                        processing_version=processing_version,
                        page_number=page_number,
                        vlm_observation=vlm_text
                    )
                    if corroborations:
                        tag_claims = [cr for cr in corroborations if cr.claim_type == "instrument_tag"]
                        num_claims = [cr for cr in corroborations if cr.claim_type in ("reading_with_unit", "numeric")]
                        if tag_claims:
                            tag_corroborated = any(cr.corroborated for cr in tag_claims)
                        if num_claims:
                            numeric_corroborated = any(cr.corroborated for cr in num_claims)
                        is_corroborated = bool(tag_corroborated or all(cr.corroborated for cr in corroborations))
            else:
                vlm_succeeded = False
        except Exception as ve:
            logger.warning(f"VLM inspection error on {filename} page {page_number}: {ve}")
            vlm_succeeded = False
            vlm_failed = True
            vlm_text = f"VLM execution error on {filename} {locator}: {ve}"

        insp_lat_ms = round((time.perf_counter() - t_insp_0) * 1000.0, 2)
        v_model_name = getattr(settings, "vision_model", "moondream:latest")

        if vlm_failed:
            status = VisualInspectionStatus.VLM_FAILED
            quality_status = ObservationQualityStatus.VLM_FAILED
            obs_valid = False
            vis_rel_obs = None
        elif not vlm_succeeded or not vlm_text.strip():
            status = VisualInspectionStatus.NO_OBSERVATION
            quality_status = ObservationQualityStatus.NO_OBSERVATION
            obs_valid = False
            vis_rel_obs = None
            if not vlm_text:
                vlm_text = f"No visual observation produced for {filename} {locator}."
        else:
            obs_valid = True
            vis_rel_obs = vlm_text
            if verification_executed:
                if tag_corroborated is True:
                    status = VisualInspectionStatus.SUCCESS
                    quality_status = ObservationQualityStatus.VERIFIED
                elif tag_corroborated is False:
                    status = VisualInspectionStatus.OBSERVED_UNCORROBORATED
                    quality_status = ObservationQualityStatus.OBSERVED_UNCORROBORATED
                else:
                    status = VisualInspectionStatus.SUCCESS
                    quality_status = ObservationQualityStatus.OBSERVED_UNCORROBORATED
            else:
                status = VisualInspectionStatus.SUCCESS
                quality_status = ObservationQualityStatus.OBSERVED_UNCORROBORATED

        return VisualInspectionResult(
            workspace_id=workspace_id,
            source_id=source_id,
            filename=filename,
            page_number=page_number,
            processing_version=processing_version,
            visual_score=visual_score,
            inspection_status=status,
            quality_status=quality_status,
            rasterized=True,
            vlm_executed=True,
            vlm_succeeded=vlm_succeeded,
            observation_valid=obs_valid,
            verification_executed=verification_executed,
            tag_corroboration=tag_corroborated,
            numeric_corroboration=numeric_corroborated,
            visual_relation_observation=vis_rel_obs,
            vlm_observation=vlm_text,
            corroboration_results=corroborations,
            ocr_corroborated=is_corroborated,
            equipment_tags=extracted_tags,
            instrument_tags=[t for t in extracted_tags if any(t.startswith(p) for p in ("PT-", "TT-", "FT-", "LT-", "VT-", "FV-", "PV-", "TV-", "HV-"))],
            observed_relations=observed_relations,
            locator=locator,
            inspection_latency_ms=insp_lat_ms,
            vlm_model=v_model_name
        )


_global_visual_inspector: Optional[VisualEvidenceInspector] = None


def get_visual_inspector() -> VisualEvidenceInspector:
    global _global_visual_inspector
    if _global_visual_inspector is None:
        _global_visual_inspector = VisualEvidenceInspector()
    return _global_visual_inspector
