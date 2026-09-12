"""
Visual Evidence Inspector for CogniShift.
Executes targeted on-demand visual page inspection via local VLM (e.g. Moondream, Qwen2.5-VL)
and corroborates visual observations with deterministic OCR verifier.
Shared across HybridDocumentRetriever and RCAEvidenceAcquirer.
"""
import time
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.core.visual_rag.schemas import CorroborationResult
from cognishift.core.visual_rag.page_cache import render_page_image_on_demand
from cognishift.core.visual_rag.page_verifier import DeterministicPageVerifier, get_page_verifier
from cognishift.core.document_processing.vision_service import VisionProcessingService
from cognishift.core.document_processing.schemas import VisionRequirement

logger = logging.getLogger(__name__)

TAG_RE = re.compile(r"\b([A-Za-z]{1,4}-\d{2,4}[A-Za-z]?)\b")


class VisualInspectionResult(BaseModel):
    """Result of targeted visual evidence inspection on a page or sheet tile."""
    workspace_id: int
    source_id: int
    filename: str
    page_number: int
    processing_version: str = "v1"
    visual_score: float = 0.0
    vlm_observation: str = ""
    corroboration_results: List[CorroborationResult] = Field(default_factory=list)
    ocr_corroborated: Optional[bool] = None
    equipment_tags: List[str] = Field(default_factory=list)
    instrument_tags: List[str] = Field(default_factory=list)
    validated_numeric_claims: List[Dict[str, Any]] = Field(default_factory=list)
    locator: str = ""
    inspection_latency_ms: float = 0.0
    vlm_model: str = ""


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
                vlm_observation=f"Visual candidate match ({filename} {locator}) with relevance score {visual_score:.2f}.",
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
                vlm_observation=f"Visual match on {filename} {locator} (rasterization unavailable).",
                locator=locator
            )

        t_insp_0 = time.perf_counter()
        target_prompt = prompt_override or (
            f"Examine this engineering diagram / schematic / document page for the query: '{query}'. "
            "Identify all visible equipment tags, line connections, flow directions, "
            "instruments, valves, setpoints, or physical anomalies. Describe the exact visual layout, piping connections, "
            "upstream/downstream relationships, and numerical labels."
        )

        vlm_text = ""
        corroborations: List[CorroborationResult] = []
        is_corroborated: Optional[bool] = None
        extracted_tags: List[str] = []

        try:
            v_obs = await self.vision_service.analyze_document_image(
                image_bytes=image_bytes,
                page_number=page_number,
                prompt=target_prompt,
                requirement=VisionRequirement.OPTIONAL
            )
            if v_obs and v_obs.description:
                vlm_text = v_obs.description.strip()

                # Extract equipment tags from observation
                for m in TAG_RE.finditer(vlm_text):
                    extracted_tags.append(m.group(1).upper())
                extracted_tags = list(dict.fromkeys(extracted_tags))

                # Deterministic OCR corroboration
                if getattr(settings, "visual_verification_enabled", True):
                    corroborations = await self.verifier.verify_page_claims(
                        workspace_id=workspace_id,
                        source_id=source_id,
                        processing_version=processing_version,
                        page_number=page_number,
                        vlm_observation=vlm_text
                    )
                    if corroborations:
                        is_corroborated = all(cr.corroborated for cr in corroborations)
        except Exception as ve:
            logger.warning(f"VLM inspection error on {filename} page {page_number}: {ve}")
            vlm_text = f"Visual match on {filename} {locator} with relevance score {visual_score:.2f}."

        if not vlm_text:
            vlm_text = f"Visual match on {filename} {locator} with relevance score {visual_score:.2f}."

        insp_lat_ms = round((time.perf_counter() - t_insp_0) * 1000.0, 2)
        v_model_name = getattr(settings, "vision_model", "moondream:latest")

        return VisualInspectionResult(
            workspace_id=workspace_id,
            source_id=source_id,
            filename=filename,
            page_number=page_number,
            processing_version=processing_version,
            visual_score=visual_score,
            vlm_observation=vlm_text,
            corroboration_results=corroborations,
            ocr_corroborated=is_corroborated,
            equipment_tags=extracted_tags,
            instrument_tags=[t for t in extracted_tags if any(t.startswith(p) for p in ("PT-", "TT-", "FT-", "LT-", "VT-", "FV-", "PV-", "TV-", "HV-"))],
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
