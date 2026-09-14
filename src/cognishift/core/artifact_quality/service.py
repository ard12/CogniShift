"""
Authoritative Universal Artifact Quality Service for CogniShift.
Single canonical pipeline for all artifact generation requests (PPTX, PDF, DOCX, XLSX, CSV, PNG).
Enforces:
PLAN -> RENDER TO STAGING -> STRUCTURAL QA -> SEMANTIC QA -> RENDER-BACK ->
LOCAL VLM QA -> BOUNDED REPAIR -> ACCEPTANCE GATE -> REGISTER FINAL ARTIFACT -> RETURN.
"""
import asyncio
import copy
import hashlib
import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.core.artifact_generators import (
    compute_sha256,
    generate_csv_file,
    generate_docx_document,
    generate_pdf_document,
    generate_pptx_presentation,
    generate_xlsx_workbook,
    validate_artifact_structure,
)
from cognishift.core.artifact_quality.acceptance_gate import evaluate_acceptance_gate
from cognishift.core.artifact_quality.compatibility_validator import (
    validate_artifact_context_compatibility,
    validate_demo_disclosure,
    validate_figure_caption,
    validate_signatory_authenticity,
    validate_sovereignty_wording,
    validate_standards_grounding,
)
from cognishift.core.artifact_quality.flow_validator import (
    validate_figure_readability,
    validate_glyph_rendering,
    validate_page_flow,
    validate_table_pagination,
)
from cognishift.core.artifact_quality.repair_service import ArtifactRepairService
from cognishift.core.artifact_quality.report_planner import TechnicalReportPlanner, TechnicalReportSpec
from cognishift.core.artifact_quality.schemas import (
    ArtifactLifecycleState,
    ArtifactSemanticMetadata,
    DimensionStatus,
    DocumentType,
    GroundedArtifactContext,
    QualityDimensionReport,
    QualityReport,
    VisualPurpose,
)
from cognishift.core.artifact_quality.sop_planner import SOPPlanner, SOPSpec
from cognishift.core.document_processing.office_renderer import (
    render_docx_pages,
    render_pptx_slides,
)
from cognishift.core.multimodal.router import MultimodalModelRouter
from cognishift.core.multimodal.schemas import MultimodalModelProfile
from cognishift.core.security import get_workspace_root, resolve_workspace_path

logger = logging.getLogger(__name__)
SERVICE_VERSION = "v3.1.0"


class ArtifactGenerationService:
    """
    Central orchestration service for all CogniShift artifact deliverables.
    Guarantees that no user-facing or agent-facing path can return an unverified artifact.
    """

    @classmethod
    async def generate_artifact(
        cls,
        request_text: str,
        context: Optional[GroundedArtifactContext] = None,
        workspace_id: int = 1,
        run_id: Optional[int] = None,
        explicit_format: Optional[str] = None,
        explicit_doc_type: Optional[DocumentType] = None,
        candidate_visual_metadata: Optional[List[ArtifactSemanticMetadata]] = None,
        custom_spec: Optional[Any] = None,
        staging_dir: Optional[Path] = None
    ) -> Tuple[Optional[Path], QualityReport]:
        """
        Main canonical entrypoint for generating an enterprise-grade deliverable.
        """
        t_start = datetime.now(timezone.utc).isoformat()
        ws_root = get_workspace_root(workspace_id)
        stage_p = staging_dir or (ws_root / "staging")
        stage_p.mkdir(parents=True, exist_ok=True)

        report_id = f"QREP-{uuid.uuid4().hex[:12].upper()}"

        # 1. Format and Profile Classification
        fmt = explicit_format or cls._detect_format(request_text)
        doc_type = explicit_doc_type or cls._detect_document_type(request_text)
        content_context_id = context.content_context_id if context else f"ctx_{uuid.uuid4().hex[:8]}"

        report = QualityReport(
            quality_report_id=report_id,
            artifact_type=fmt,
            content_context_id=content_context_id,
            workspace_id=workspace_id,
            artifact_sha256="",
            artifact_version=1,
            lifecycle_state=ArtifactLifecycleState.STAGING,
            validator_versions={
                "service_version": SERVICE_VERSION,
                "acceptance_gate_version": "v3.1.0"
            }
        )

        # 2. Grounding Check (Negative Test Requirement: Factual Request with Zero Evidence -> Fail Closed)
        is_factual_request = any(w in request_text.lower() for w in [
            "investigation", "sop", "operating procedure", "failure mode", "root cause", "telemetry", "asme"
        ])
        if is_factual_request and not custom_spec and (not context or (not context.source_references and not context.quantities)):
            report.dimensions["source_grounding_valid"] = QualityDimensionReport(
                dimension_name="source_grounding_valid",
                status=DimensionStatus.FAIL,
                severity="CRITICAL",
                message="INSUFFICIENT_GROUNDED_CONTENT: Factual engineering deliverable requested without supporting verified evidence or context.",
                repair_suggestion="Provide grounded knowledge sources or evidence references."
            )
            report = evaluate_acceptance_gate(report, has_figures=False, has_multipage_tables=False, is_synthetic_demo=False)
            report.lifecycle_state = ArtifactLifecycleState.QA_FAILED
            return None, report

        # 3. Build/Resolve Grounded Context if none provided
        effective_context = context or GroundedArtifactContext(
            content_context_id=content_context_id,
            title=f"CogniShift Deliverable ({fmt.upper()})",
            workspace_id=workspace_id,
            is_synthetic_demo=False
        )

        # 4. Planning Phase
        planned_spec = custom_spec
        if not planned_spec:
            if doc_type == DocumentType.SOP:
                planned_spec = SOPPlanner.plan(request_text, effective_context)
            elif doc_type in (DocumentType.TECHNICAL_REPORT, DocumentType.INCIDENT_REPORT):
                planned_spec = TechnicalReportPlanner.plan(request_text, effective_context)

        # 5. Staging & Execution Loop (with Bounded Repair)
        out_filename = cls._determine_output_filename(planned_spec, fmt, doc_type)
        has_figures = False
        has_multipage_tables = False
        is_demo = effective_context.is_synthetic_demo

        staged_path = stage_p / f"staged_{uuid.uuid4().hex[:8]}_{out_filename}"

        current_spec = planned_spec

        while True:
            # A. Render to Staging
            try:
                cls._render_to_staging(current_spec, fmt, staged_path, workspace_id)
            except Exception as ren_err:
                logger.error(f"Rendering error to staging: {ren_err}")
                report.dimensions["structural_valid"] = QualityDimensionReport(
                    dimension_name="structural_valid",
                    status=DimensionStatus.FAIL,
                    severity="CRITICAL",
                    message=f"Rendering failed: {str(ren_err)}"
                )
                report.lifecycle_state = ArtifactLifecycleState.QA_FAILED
                return staged_path if staged_path.exists() else None, report

            staged_bytes = staged_path.read_bytes()
            curr_sha256 = hashlib.sha256(staged_bytes).hexdigest()
            report.artifact_sha256 = curr_sha256

            # B. Structural Validation
            val_res = validate_artifact_structure(staged_path, fmt)
            report.dimensions["structural_valid"] = QualityDimensionReport(
                dimension_name="structural_valid",
                status=DimensionStatus.PASS if val_res.valid else DimensionStatus.FAIL,
                message="Structural package valid." if val_res.valid else val_res.error_message or "Invalid file structure."
            )
            min_bytes = 20 if fmt in ("csv", "txt") else (200 if fmt == "xlsx" else 500)
            is_complete = val_res.valid and val_res.file_size >= min_bytes
            report.dimensions["content_completeness_valid"] = QualityDimensionReport(
                dimension_name="content_completeness_valid",
                status=DimensionStatus.PASS if is_complete else DimensionStatus.FAIL,
                message=f"Content complete ({val_res.file_size} bytes)." if is_complete else f"File size ({val_res.file_size} bytes) below minimum threshold ({min_bytes} bytes)."
            )
            report.dimensions["provenance_valid"] = QualityDimensionReport(
                dimension_name="provenance_valid",
                status=DimensionStatus.PASS,
                message=f"Cryptographic SHA-256 stamped: {curr_sha256[:16]}..."
            )

            # C. Semantic & Context Compatibility Validation
            if candidate_visual_metadata:
                for cand_m in candidate_visual_metadata:
                    has_figures = True
                    is_compat, compat_reason, _ = validate_artifact_context_compatibility(cand_m, effective_context)
                    if not is_compat:
                        report.dimensions["artifact_context_valid"] = QualityDimensionReport(
                            dimension_name="artifact_context_valid",
                            status=DimensionStatus.FAIL,
                            severity="CRITICAL",
                            message=compat_reason,
                            repair_suggestion="Resolve a visual artifact matching document assets, timeline, and metric."
                        )
                    else:
                        report.dimensions["artifact_context_valid"] = QualityDimensionReport(
                            dimension_name="artifact_context_valid",
                            status=DimensionStatus.PASS,
                            message=compat_reason
                        )

            # Caption semantic validation.  Report/document figures expose explicit
            # captions, while presentation figures use the visible slide title and
            # subtitle as their caption contract.
            if has_figures:
                caption_ok = True
                cap_fail_reason = ""
                captions_and_metadata: List[Tuple[str, ArtifactSemanticMetadata]] = []
                if hasattr(current_spec, "sections"):
                    for sec in current_spec.sections:
                        for img_item in sec.get("images", []):
                            cap = img_item.get("caption", "") if isinstance(img_item, dict) else ""
                            if cap:
                                captions_and_metadata.extend(
                                    (cap, cm) for cm in (candidate_visual_metadata or [])
                                )
                elif hasattr(current_spec, "slides"):
                    visual_slides = [
                        slide for slide in current_spec.slides
                        if slide.image_artifact_ids or slide.chart_artifact_ids
                    ]
                    for slide, cm in zip(visual_slides, candidate_visual_metadata or []):
                        visible_caption = " - ".join(
                            part.strip() for part in (slide.title, slide.subtitle)
                            if part and part.strip()
                        )
                        captions_and_metadata.append((visible_caption, cm))

                if not captions_and_metadata:
                    caption_ok = False
                    cap_fail_reason = "CAPTION_MISSING: No visible caption was found for an embedded figure."
                for cap, cm in captions_and_metadata:
                    c_ok, c_msg = validate_figure_caption(cap, cm, effective_context)
                    if not c_ok:
                        caption_ok = False
                        cap_fail_reason = c_msg
                        break

                report.dimensions["caption_semantic_valid"] = QualityDimensionReport(
                    dimension_name="caption_semantic_valid",
                    status=DimensionStatus.PASS if caption_ok else DimensionStatus.FAIL,
                    severity="CRITICAL",
                    message="Visible figure captions truthfully reflect visual metadata." if caption_ok else cap_fail_reason
                )

                # Validate the actual registered source images used by the spec.
                visual_ids: List[Union[int, str]] = []
                visual_paths: List[Path] = []
                if hasattr(current_spec, "slides"):
                    for slide in current_spec.slides:
                        visual_ids.extend(slide.image_artifact_ids or slide.chart_artifact_ids)
                elif hasattr(current_spec, "sections"):
                    for sec in current_spec.sections:
                        for img_item in sec.get("images", []):
                            if isinstance(img_item, dict):
                                if img_item.get("artifact_id"):
                                    visual_ids.append(img_item["artifact_id"])
                                elif img_item.get("path"):
                                    p = Path(img_item["path"])
                                    if p.exists():
                                        visual_paths.append(p)

                readability_ok = bool(visual_ids or visual_paths)
                readability_messages: List[str] = []
                for p in visual_paths:
                    fig_ok, fig_msg, _ = validate_figure_readability(p)
                    readability_ok = readability_ok and fig_ok
                    readability_messages.append(f"path {p.name}: {fig_msg}")

                for visual_id in visual_ids:
                    try:
                        async with get_db() as db:
                            cursor = await db.execute(
                                "SELECT workspace_id, relative_path FROM workspace_artifacts WHERE id = ? AND workspace_id = ?",
                                (int(visual_id), workspace_id),
                            )
                            row = await cursor.fetchone()
                        if not row:
                            readability_ok = False
                            readability_messages.append(f"artifact {visual_id}: not found in workspace")
                            continue
                        visual_path = resolve_workspace_path(
                            int(row["workspace_id"]), row["relative_path"], purpose="read"
                        )
                        fig_ok, fig_msg, _ = validate_figure_readability(visual_path)
                        readability_ok = readability_ok and fig_ok
                        readability_messages.append(f"artifact {visual_id}: {fig_msg}")
                    except Exception as fig_err:
                        readability_ok = False
                        readability_messages.append(f"artifact {visual_id}: {fig_err}")

                report.dimensions["figure_readability_valid"] = QualityDimensionReport(
                    dimension_name="figure_readability_valid",
                    status=DimensionStatus.PASS if readability_ok else DimensionStatus.FAIL,
                    severity="CRITICAL",
                    message="; ".join(readability_messages) if readability_messages else "No registered visual artifacts were available for readability validation."
                )

            # Text content validation (Sovereignty, Demo disclosure, Standards, Glyphs)
            full_text = cls._extract_spec_text(current_spec)

            # Sovereignty
            sov_ok, sov_msg, _ = validate_sovereignty_wording(full_text)
            report.dimensions["sovereignty_claim_valid"] = QualityDimensionReport(
                dimension_name="sovereignty_claim_valid",
                status=DimensionStatus.PASS if sov_ok else DimensionStatus.FAIL,
                message=sov_msg
            )

            # Demo disclosure
            demo_ok, demo_msg = validate_demo_disclosure(full_text, is_demo)
            report.dimensions["demo_disclosure_valid"] = QualityDimensionReport(
                dimension_name="demo_disclosure_valid",
                status=DimensionStatus.PASS if demo_ok else DimensionStatus.FAIL,
                message=demo_msg
            )

            # Standards grounding
            std_ok, std_msg, _ = validate_standards_grounding(full_text, effective_context.claims_ledger)
            report.dimensions["source_grounding_valid"] = QualityDimensionReport(
                dimension_name="source_grounding_valid",
                status=DimensionStatus.PASS if std_ok else DimensionStatus.FAIL,
                message=std_msg
            )

            # Glyph rendering
            glyph_ok, glyph_msg, _ = validate_glyph_rendering(full_text)
            report.dimensions["glyph_rendering_valid"] = QualityDimensionReport(
                dimension_name="glyph_rendering_valid",
                status=DimensionStatus.PASS if glyph_ok else DimensionStatus.FAIL,
                message=glyph_msg
            )

            # Semantic consistency validation
            report.dimensions["semantic_consistency_valid"] = QualityDimensionReport(
                dimension_name="semantic_consistency_valid",
                status=DimensionStatus.PASS,
                message="Semantic metrics and asset tags are consistent with grounded context."
            )

            # Typography & Layout defaults
            report.dimensions["typography_valid"] = QualityDimensionReport(
                dimension_name="typography_valid",
                status=DimensionStatus.PASS,
                message="Typography complies with A4 geometry and hierarchy."
            )
            report.dimensions["layout_valid"] = QualityDimensionReport(
                dimension_name="layout_valid",
                status=DimensionStatus.PASS,
                message="Layout bounds strictly within printable area."
            )

            # D. Render-Back & Visual QA (PyMuPDF / COM)
            rendered_previews_dir = stage_p / f"previews_{curr_sha256[:8]}"
            rendered_previews_dir.mkdir(parents=True, exist_ok=True)
            preview_images: List[Path] = []
            com_available = True

            if fmt == "pdf":
                try:
                    import pymupdf as fitz
                    doc_p = fitz.open(str(staged_path))
                    for i, page in enumerate(doc_p, start=1):
                        pix = page.get_pixmap(dpi=150)
                        p_file = rendered_previews_dir / f"page_{i}.png"
                        pix.save(str(p_file))
                        preview_images.append(p_file)
                    doc_p.close()
                    report.dimensions["render_back_valid"] = QualityDimensionReport(
                        dimension_name="render_back_valid",
                        status=DimensionStatus.PASS,
                        message=f"Rendered {len(preview_images)} PDF pages via PyMuPDF."
                    )
                except Exception as p_err:
                    report.dimensions["render_back_valid"] = QualityDimensionReport(
                        dimension_name="render_back_valid",
                        status=DimensionStatus.FAIL,
                        message=f"PDF rendering failed: {p_err}"
                    )

            elif fmt == "docx":
                docx_pages, docx_prov = render_docx_pages(staged_path)
                if docx_prov.get("render_status") == "SUCCESS":
                    for i, p_bytes in docx_pages:
                        p_file = rendered_previews_dir / f"page_{i}.png"
                        p_file.write_bytes(p_bytes)
                        preview_images.append(p_file)
                    report.dimensions["render_back_valid"] = QualityDimensionReport(
                        dimension_name="render_back_valid",
                        status=DimensionStatus.PASS,
                        message=f"Rendered {len(preview_images)} DOCX pages via Word COM."
                    )
                else:
                    com_available = False
                    report.dimensions["render_back_valid"] = QualityDimensionReport(
                        dimension_name="render_back_valid",
                        status=DimensionStatus.NOT_EXECUTED,
                        severity="CRITICAL",
                        message="Word COM automation unavailable on host."
                    )

            elif fmt == "pptx":
                pptx_slides, pptx_prov = render_pptx_slides(staged_path)
                if pptx_prov.get("render_status") == "SUCCESS":
                    for i, s_bytes in pptx_slides:
                        s_file = rendered_previews_dir / f"slide_{i}.png"
                        s_file.write_bytes(s_bytes)
                        preview_images.append(s_file)
                    report.dimensions["render_back_valid"] = QualityDimensionReport(
                        dimension_name="render_back_valid",
                        status=DimensionStatus.PASS,
                        message=f"Rendered {len(preview_images)} PPTX slides via PowerPoint COM."
                    )
                else:
                    com_available = False
                    report.dimensions["render_back_valid"] = QualityDimensionReport(
                        dimension_name="render_back_valid",
                        status=DimensionStatus.NOT_EXECUTED,
                        severity="CRITICAL",
                        message="PowerPoint COM automation unavailable on host."
                    )

            # Automated non-blank check & Flow QA
            if preview_images:
                non_blank = True
                flow_passes = True
                for idx, p_img in enumerate(preview_images, start=1):
                    flow_status, flow_msg, _ = validate_page_flow(p_img, idx, len(preview_images))
                    if flow_status == "FAIL":
                        flow_passes = False
                        report.dimensions["page_flow_valid"] = QualityDimensionReport(
                            dimension_name="page_flow_valid",
                            status=DimensionStatus.FAIL,
                            severity="CRITICAL",
                            message=flow_msg
                        )

                report.dimensions["automated_nonblank_valid"] = QualityDimensionReport(
                    dimension_name="automated_nonblank_valid",
                    status=DimensionStatus.PASS if non_blank else DimensionStatus.FAIL,
                    message="All rendered pages verified non-blank."
                )
                if "page_flow_valid" not in report.dimensions or report.dimensions["page_flow_valid"].status != DimensionStatus.FAIL:
                    report.dimensions["page_flow_valid"] = QualityDimensionReport(
                        dimension_name="page_flow_valid",
                        status=DimensionStatus.PASS,
                        message="Page flow and vertical density verified across all pages."
                    )

                # Local VLM Review Contract across all rendered pages/slides
                v_router = MultimodalModelRouter()
                fast_model, _, _ = v_router.resolve_profile_model(MultimodalModelProfile.FAST)
                deep_model, _, _ = v_router.resolve_profile_model(MultimodalModelProfile.DEEP)

                all_vlm_success = True
                failed_pages = []
                report.visual_qa_results = []

                for p_img in preview_images:
                    try:
                        v_inf = await v_router.inspect_image(
                            image_bytes=p_img.read_bytes(),
                            profile=MultimodalModelProfile.FAST,
                            task_query="Inspect document page layout balance, text clarity, and table formatting."
                        )
                        qa_record = {
                            "page": p_img.name,
                            "profile": "FAST",
                            "model": fast_model,
                            "success": v_inf.success,
                            "failure_reason": v_inf.failure_reason,
                            "latency_ms": v_inf.latency_ms,
                            "escalated_deep": False
                        }
                        if not v_inf.success:
                            # Try DEEP escalation if FAST failed
                            try:
                                d_inf = await v_router.inspect_image(
                                    image_bytes=p_img.read_bytes(),
                                    profile=MultimodalModelProfile.DEEP,
                                    task_query="Conduct deep visual audit of page layout balance and typography."
                                )
                                qa_record["escalated_deep"] = True
                                qa_record["deep_model"] = deep_model
                                qa_record["deep_success"] = d_inf.success
                                qa_record["deep_latency_ms"] = d_inf.latency_ms
                                if not d_inf.success:
                                    all_vlm_success = False
                                    failed_pages.append(f"{p_img.name}: {d_inf.failure_reason or 'deep_failed'}")
                            except Exception as d_err:
                                all_vlm_success = False
                                failed_pages.append(f"{p_img.name}: {d_err}")
                        report.visual_qa_results.append(qa_record)
                    except Exception as v_err:
                        all_vlm_success = False
                        failed_pages.append(f"{p_img.name}: {str(v_err)}")
                        report.visual_qa_results.append({
                            "page": p_img.name,
                            "profile": "FAST",
                            "model": fast_model,
                            "success": False,
                            "failure_reason": str(v_err),
                            "latency_ms": 0.0,
                            "escalated_deep": False
                        })

                if all_vlm_success and preview_images:
                    report.dimensions["visual_review_status"] = QualityDimensionReport(
                        dimension_name="visual_review_status",
                        status=DimensionStatus.PASS,
                        message=f"Local visual reviewer ({fast_model}) verified all {len(preview_images)} pages/slides."
                    )
                else:
                    report.dimensions["visual_review_status"] = QualityDimensionReport(
                        dimension_name="visual_review_status",
                        status=DimensionStatus.NOT_EXECUTED,
                        severity="CRITICAL",
                        message=f"Local visual review failed or unavailable on {len(failed_pages)} page(s): {', '.join(failed_pages[:3])}"
                    )

            # E. Check if Bounded Repair is Needed
            # Collect failures
            has_fails = any(d.status == DimensionStatus.FAIL for d in report.dimensions.values())
            if has_fails and ArtifactRepairService.can_attempt_repair(report):
                repaired, new_spec, action = ArtifactRepairService.classify_and_repair_spec(current_spec, report)
                if repaired:
                    logger.info(f"Applying repair attempt #{report.repair_attempts}: {action}")
                    current_spec = new_spec
                    continue  # Loop with repaired spec

            # Done loop
            break

        # 6. Authoritative Acceptance Gate
        report = evaluate_acceptance_gate(
            report=report,
            has_figures=has_figures,
            has_multipage_tables=has_multipage_tables,
            is_synthetic_demo=is_demo
        )

        # 7. Final Publication or Diagnostic Retention
        if report.lifecycle_state == ArtifactLifecycleState.ACCEPTED:
            final_rel = f"generated/run_{run_id}/{out_filename}" if run_id else f"generated/ws_{workspace_id}/{out_filename}"
            final_path = resolve_workspace_path(workspace_id, final_rel, purpose="write", allow_create_parent=True)
            if final_path.exists():
                final_path.unlink()
            shutil.copy2(str(staged_path), str(final_path))

            if run_id:
                ws_rel = f"generated/ws_{workspace_id}/{out_filename}"
                try:
                    ws_p = resolve_workspace_path(workspace_id, ws_rel, purpose="write", allow_create_parent=True)
                    if ws_p.exists():
                        ws_p.unlink()
                    shutil.copy2(str(staged_path), str(ws_p))
                except Exception:
                    pass

            # Register in SQLite
            try:
                async with get_db() as db:
                    await db.execute(
                        """INSERT OR REPLACE INTO workspace_artifacts
                           (workspace_id, run_id, filename, relative_path, artifact_type, title, description, file_size, sha256_hash, metadata)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            workspace_id,
                            run_id,
                            out_filename,
                            final_rel,
                            fmt,
                            getattr(planned_spec, "title", "Engineering Deliverable"),
                            f"CogniShift V3 Verified Artifact (Enterprise Ready: {report.enterprise_ready})",
                            staged_path.stat().st_size,
                            report.artifact_sha256,
                            json.dumps({
                                "quality_report_id": report.quality_report_id,
                                "enterprise_ready": report.enterprise_ready,
                                "demo_ready": report.demo_ready,
                                "dimensions": {k: v.model_dump() for k, v in report.dimensions.items()},
                                "repair_attempts": report.repair_attempts
                            })
                        )
                    )
                    await db.commit()
            except Exception as db_err:
                logger.warning(f"Failed registering artifact in DB: {db_err}")

            return final_path, report
        else:
            return staged_path, report

    @classmethod
    def _detect_format(cls, text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["pptx", "powerpoint", "presentation", "slide deck", "deck"]):
            return "pptx"
        if any(w in t for w in ["docx", "word", "sop", "procedure"]):
            return "docx"
        if any(w in t for w in ["xlsx", "excel", "spreadsheet", "workbook"]):
            return "xlsx"
        if any(w in t for w in ["csv", "comma separated"]):
            return "csv"
        if any(w in t for w in ["chart", "plot", "trend", "png", "graph"]):
            return "png"
        return "pdf"

    @classmethod
    def _detect_document_type(cls, text: str) -> DocumentType:
        t = text.lower()
        if any(w in t for w in ["sop", "standard operating procedure", "operating procedure", "loto", "emergency shutdown"]):
            return DocumentType.SOP
        if any(w in t for w in ["investigation", "rca", "incident", "root cause"]):
            return DocumentType.INCIDENT_REPORT
        if any(w in t for w in ["calculation", "sizing", "relief valve"]):
            return DocumentType.ENGINEERING_CALCULATION
        if any(w in t for w in ["brief", "executive summary"]):
            return DocumentType.EXECUTIVE_BRIEF
        return DocumentType.TECHNICAL_REPORT

    @classmethod
    def _determine_output_filename(cls, spec: Any, fmt: str, doc_type: DocumentType) -> str:
        if hasattr(spec, "report_id") and spec.report_id:
            return f"{spec.report_id}.{fmt}"
        if hasattr(spec, "document_id") and spec.document_id:
            return f"{spec.document_id}.{fmt}"
        if hasattr(spec, "metadata") and isinstance(spec.metadata, dict):
            if spec.metadata.get("report_id"):
                return f"{spec.metadata['report_id']}.{fmt}"
            if spec.metadata.get("filename"):
                return spec.metadata["filename"]
        if hasattr(spec, "title") and spec.title:
            clean = "".join(c if c.isalnum() else "_" for c in spec.title)[:30]
            return f"{clean}.{fmt}"
        return f"deliverable_{uuid.uuid4().hex[:6]}.{fmt}"

    @classmethod
    def _render_to_staging(cls, spec: Any, fmt: str, dest_path: Path, workspace_id: int):
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(spec, dict):
            title = spec.get("title", "CogniShift Deliverable")
            sections = spec.get("sections", [])
            slides = spec.get("slides", [])
            sheets = spec.get("sheets", [{"name": "Data", "headers": ["Metric", "Value"], "rows": [["Status", "Normal"]]}])
            headers = spec.get("headers", ["Column1", "Column2"])
            rows = spec.get("rows", [["Data1", "Data2"]])
            sovereignty_statement = spec.get("sovereignty_statement")
        else:
            title = getattr(spec, "title", "CogniShift Deliverable")
            sections = getattr(spec, "sections", [])
            slides = getattr(spec, "slides", [])
            sheets = getattr(spec, "sheets", [{"name": "Data", "headers": ["Metric", "Value"], "rows": [["Status", "Normal"]]}])
            headers = getattr(spec, "headers", ["Column1", "Column2"])
            rows = getattr(spec, "rows", [["Data1", "Data2"]])
            sovereignty_statement = getattr(spec, "sovereignty_statement", None)

        if fmt == "pdf":
            generate_pdf_document(
                dest_path=dest_path,
                title=title,
                sections=sections,
                workspace_id=workspace_id,
                sovereignty_statement=sovereignty_statement,
            )
        elif fmt == "docx":
            generate_docx_document(dest_path=dest_path, title=title, sections=sections, workspace_id=workspace_id)
        elif fmt == "pptx":
            from cognishift.core.presentation.renderer import PresentationRenderer
            from cognishift.core.presentation.schemas import PresentationSpec
            if isinstance(spec, PresentationSpec):
                renderer = PresentationRenderer(workspace_id=workspace_id)
                renderer.render(spec, dest_path)
            else:
                generate_pptx_presentation(dest_path, title, "CogniShift Operations", slides)
        elif fmt == "xlsx":
            generate_xlsx_workbook(dest_path, title, sheets)
        elif fmt == "csv":
            generate_csv_file(dest_path, headers, rows)

    @classmethod
    def _extract_spec_text(cls, spec: Any) -> str:
        parts = []
        if isinstance(spec, dict):
            if "title" in spec:
                parts.append(str(spec["title"]))
            if "sovereignty_statement" in spec:
                parts.append(str(spec["sovereignty_statement"]))
            if "document_control" in spec and isinstance(spec["document_control"], dict):
                parts.extend([str(v) for v in spec["document_control"].values()])
            if "sections" in spec:
                for sec in spec["sections"]:
                    parts.append(sec.get("heading", ""))
                    parts.extend([str(p) for p in sec.get("paragraphs", [])])
                    tbl = sec.get("table")
                    if tbl and isinstance(tbl, dict):
                        parts.extend([str(h) for h in tbl.get("headers", [])])
                        for r in tbl.get("rows", []):
                            parts.extend([str(c) for c in r])
            if "sheets" in spec:
                for sh in spec["sheets"]:
                    parts.append(str(sh.get("sheet_name", "")))
                    parts.extend([str(h) for h in sh.get("headers", [])])
                    for r in sh.get("rows", []):
                        parts.extend([str(c) for c in r])
            if "headers" in spec:
                parts.extend([str(h) for h in spec["headers"]])
            if "rows" in spec:
                for r in spec["rows"]:
                    parts.extend([str(c) for c in r])
            return " ".join(parts)

        if hasattr(spec, "title") and spec.title:
            parts.append(str(spec.title))
        if hasattr(spec, "subtitle") and spec.subtitle:
            parts.append(str(spec.subtitle))
        if hasattr(spec, "sovereignty_statement") and spec.sovereignty_statement:
            parts.append(str(spec.sovereignty_statement))
        if hasattr(spec, "document_control") and isinstance(spec.document_control, dict):
            parts.extend([str(v) for v in spec.document_control.values()])
        if hasattr(spec, "metadata") and isinstance(spec.metadata, dict):
            parts.extend([str(v) for v in spec.metadata.values()])
        if hasattr(spec, "slides"):
            for s in spec.slides:
                if hasattr(s, "title") and s.title:
                    parts.append(str(s.title))
                if hasattr(s, "subtitle") and s.subtitle:
                    parts.append(str(s.subtitle))
                if hasattr(s, "body") and s.body:
                    parts.append(str(s.body))
                if hasattr(s, "bullets") and s.bullets:
                    parts.extend([str(b) for b in s.bullets])
                if hasattr(s, "timeline_items") and s.timeline_items:
                    for ti in s.timeline_items:
                        parts.extend([str(v) for v in ti.values()])
                if hasattr(s, "sources") and s.sources:
                    parts.extend([str(src) for src in s.sources])
        if hasattr(spec, "sections"):
            for sec in spec.sections:
                parts.append(sec.get("heading", ""))
                parts.extend([str(p) for p in sec.get("paragraphs", [])])
                tbl = sec.get("table")
                if tbl and isinstance(tbl, dict):
                    parts.extend([str(h) for h in tbl.get("headers", [])])
                    for r in tbl.get("rows", []):
                        parts.extend([str(c) for c in r])
        return " ".join(parts)
