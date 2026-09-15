"""
Structural OpenXML and Canonical Provenance Validator for PPTX presentations.
Verifies ZIP structure, slide counts, and confirms embedded media matches registered SHA-256 digests.
"""
import hashlib
import zipfile
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import pptx

logger = logging.getLogger(__name__)


@dataclass
class PresentationValidationReport:
    valid: bool
    slide_count: int
    file_size: int
    sha256_hash: str
    media_files_verified: int = 0
    matched_media_shas: List[str] = field(default_factory=list)
    unmatched_media_shas: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    # Disaggregated QA dimensions (SIH Review Amendments)
    structural_valid: bool = False
    content_completeness_valid: bool = True
    missing_content_elements: Dict[int, List[str]] = field(default_factory=dict)
    provenance_valid: bool = True
    typography_valid: bool = True
    layout_valid: bool = True
    render_back_valid: bool = False
    automated_nonblank_valid: bool = False
    automated_bounds_valid: bool = True
    visual_review_status: str = "PENDING"
    demo_ready: bool = False

    minimum_font_pt_detected: float = 0.0
    font_size_violations: List[str] = field(default_factory=list)
    layout_anomalies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "demo_ready": self.demo_ready,
            "structural_valid": self.structural_valid,
            "content_completeness_valid": self.content_completeness_valid,
            "missing_content_elements": self.missing_content_elements,
            "provenance_valid": self.provenance_valid,
            "typography_valid": self.typography_valid,
            "layout_valid": self.layout_valid,
            "render_back_valid": self.render_back_valid,
            "automated_nonblank_valid": self.automated_nonblank_valid,
            "automated_bounds_valid": self.automated_bounds_valid,
            "visual_review_status": self.visual_review_status,
            "slide_count": self.slide_count,
            "file_size": self.file_size,
            "sha256_hash": self.sha256_hash,
            "media_files_verified": self.media_files_verified,
            "matched_media_shas": self.matched_media_shas,
            "unmatched_media_shas": self.unmatched_media_shas,
            "minimum_font_pt_detected": self.minimum_font_pt_detected,
            "font_size_violations": self.font_size_violations,
            "layout_anomalies": self.layout_anomalies,
            "error_message": self.error_message,
        }


class PresentationValidator:
    """Validates physical integrity, content completeness, typography, and media provenance of PPTX artifacts."""

    @classmethod
    def validate_presentation_file(
        cls,
        file_path: Path,
        expected_slide_count: Optional[int] = None,
        expected_media_shas: Optional[List[str]] = None,
        spec: Optional[Any] = None,
    ) -> PresentationValidationReport:
        if not file_path.exists():
            return PresentationValidationReport(
                valid=False,
                slide_count=0,
                file_size=0,
                sha256_hash="",
                error_message="File does not exist on disk.",
                structural_valid=False,
                demo_ready=False,
            )

        file_size = file_path.stat().st_size
        if file_size == 0:
            return PresentationValidationReport(
                valid=False,
                slide_count=0,
                file_size=0,
                sha256_hash="",
                error_message="Presentation file is empty (0 bytes).",
                structural_valid=False,
                demo_ready=False,
            )

        file_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()

        # 1. Verify OpenXML / ZIP packaging
        try:
            with zipfile.ZipFile(str(file_path), "r") as zf:
                namelist = zf.namelist()
                if "[Content_Types].xml" not in namelist:
                    return PresentationValidationReport(
                        valid=False,
                        slide_count=0,
                        file_size=file_size,
                        sha256_hash=file_sha256,
                        error_message="Invalid OpenXML structure: missing [Content_Types].xml",
                        structural_valid=False,
                        demo_ready=False,
                    )
                if "ppt/presentation.xml" not in namelist:
                    return PresentationValidationReport(
                        valid=False,
                        slide_count=0,
                        file_size=file_size,
                        sha256_hash=file_sha256,
                        error_message="Invalid OpenXML structure: missing ppt/presentation.xml",
                        structural_valid=False,
                        demo_ready=False,
                    )

                # 2. Extract media digests from ppt/media/*
                media_shas = []
                for name in namelist:
                    if name.startswith("ppt/media/"):
                        m_bytes = zf.read(name)
                        m_hash = hashlib.sha256(m_bytes).hexdigest()
                        media_shas.append(m_hash)
        except Exception as ze:
            return PresentationValidationReport(
                valid=False,
                slide_count=0,
                file_size=file_size,
                sha256_hash=file_sha256,
                error_message=f"ZIP archive corrupted: {ze}",
                structural_valid=False,
                demo_ready=False,
            )

        # 3. Verify python-pptx reopens successfully
        try:
            prs = pptx.Presentation(str(file_path))
            actual_slides = len(prs.slides)
            if expected_slide_count is not None and actual_slides != expected_slide_count:
                return PresentationValidationReport(
                    valid=False,
                    slide_count=actual_slides,
                    file_size=file_size,
                    sha256_hash=file_sha256,
                    error_message=f"Slide count mismatch: expected {expected_slide_count}, got {actual_slides}",
                    structural_valid=False,
                    demo_ready=False,
                )
        except Exception as pe:
            return PresentationValidationReport(
                valid=False,
                slide_count=0,
                file_size=file_size,
                sha256_hash=file_sha256,
                error_message=f"Failed opening presentation with python-pptx: {pe}",
                structural_valid=False,
                demo_ready=False,
            )

        structural_valid = True

        # 4. Content Completeness Check (Pre-declared required elements contract)
        content_completeness_valid = True
        missing_content_elements = {}
        if spec is not None and hasattr(spec, "slides"):
            rendered_by_slide = spec.metadata.get("rendered_elements_by_slide", {}) if hasattr(spec, "metadata") else {}
            for s_idx, slide in enumerate(spec.slides, start=1):
                req = set(getattr(slide, "required_elements", []) or [])
                if req:
                    rend = set(rendered_by_slide.get(s_idx, []))
                    diff = req - rend
                    if diff:
                        content_completeness_valid = False
                        missing_content_elements[s_idx] = sorted(list(diff))

        # 5. Deterministic Layout, Bounds & Typography Validation
        layout_anomalies = []
        font_violations = []
        min_font_pt = 999.0

        try:
            slide_w_pts = prs.slide_width.pt
            slide_h_pts = prs.slide_height.pt
            for s_idx, slide in enumerate(prs.slides, start=1):
                for shape in slide.shapes:
                    left_pt = shape.left.pt if shape.left else 0
                    top_pt = shape.top.pt if shape.top else 0
                    w_pt = shape.width.pt if shape.width else 0
                    h_pt = shape.height.pt if shape.height else 0

                    if w_pt < 0 or h_pt < 0:
                        layout_anomalies.append(f"Slide {s_idx}: Negative shape dimension ({w_pt}x{h_pt})")
                    if left_pt < -10 or top_pt < -10:
                        layout_anomalies.append(f"Slide {s_idx}: Shape positioned outside left/top bounds ({left_pt}, {top_pt})")
                    if (left_pt + w_pt) > (slide_w_pts + 50) or (top_pt + h_pt) > (slide_h_pts + 50):
                        layout_anomalies.append(f"Slide {s_idx}: Shape exceeds slide boundary ({left_pt + w_pt} > {slide_w_pts})")

                    if shape.has_text_frame:
                        if len(shape.text_frame.paragraphs) > 14:
                            layout_anomalies.append(f"Slide {s_idx}: Excessive paragraph count ({len(shape.text_frame.paragraphs)}) in text frame")

                        is_footer = (top_pt > 450)
                        for p in shape.text_frame.paragraphs:
                            p_text = p.text.strip()
                            if not p_text:
                                continue
                            pt_size = None
                            if p.font and p.font.size:
                                pt_size = p.font.size.pt
                            elif p.runs:
                                for r in p.runs:
                                    if r.font and r.font.size:
                                        pt_size = r.font.size.pt
                                        break
                            if pt_size is not None:
                                if pt_size < min_font_pt:
                                    min_font_pt = pt_size
                                # Typography Validation Contract (SIH Review Amendment #1):
                                # - Slide 1 title slide: title >= 34pt, subtitle >= 16pt, kicker/footer >= 9.5pt
                                # - Footers / non-primary metadata: 10-12pt allowed
                                # - Short card labels, timestamps, KPI subtext: 10-12pt allowed
                                # - Primary body copy & bullet narratives: >= 16pt (standard 18-22pt)
                                # - Never shrink primary body below 16pt threshold
                                if s_idx == 1:
                                    if pt_size < 9.5:
                                        font_violations.append(
                                            f"Slide 1: Text '{p_text[:35]}...' set to {pt_size}pt < 9.5pt."
                                        )
                                elif is_footer:
                                    if pt_size < 9.5:
                                        font_violations.append(
                                            f"Slide {s_idx} Footer: Text '{p_text[:35]}...' set to {pt_size}pt < 9.5pt."
                                        )
                                elif len(p_text) > 40:  # Substantive narrative body paragraph
                                    if pt_size < 15.5:
                                        font_violations.append(
                                            f"Slide {s_idx} Body: Text '{p_text[:35]}...' set to {pt_size}pt violates 16pt primary body threshold."
                                        )
                                else:  # Short metadata, kicker, badge, or card label
                                    if pt_size < 9.5:
                                        font_violations.append(
                                            f"Slide {s_idx} Metadata: Text '{p_text[:35]}...' set to {pt_size}pt < 9.5pt."
                                        )

                    # Inspect table cell typography
                    if shape.has_table:
                        for row in shape.table.rows:
                            for cell in row.cells:
                                for p in cell.text_frame.paragraphs:
                                    if p.font and p.font.size:
                                        sz = p.font.size.pt
                                        if sz < min_font_pt:
                                            min_font_pt = sz
                                        if sz < 11.5:
                                            font_violations.append(
                                                f"Slide {s_idx} Table: Cell text '{p.text.strip()[:25]}' set to {sz}pt < 12pt."
                                            )
        except Exception as le:
            logger.warning(f"Error checking presentation layout bounds: {le}")

        if min_font_pt == 999.0:
            min_font_pt = 0.0

        layout_valid = (len(layout_anomalies) == 0)
        automated_bounds_valid = layout_valid
        typography_valid = (len(font_violations) == 0)

        # 6. Provenance & Media SHA-256 Matching
        matched = []
        unmatched = []
        if expected_media_shas:
            for exp in expected_media_shas:
                if exp in media_shas:
                    matched.append(exp)
                else:
                    unmatched.append(exp)

        provenance_valid = (len(unmatched) == 0)
        valid = structural_valid and provenance_valid

        error_message = None
        if unmatched:
            error_message = f"Missing expected media artifacts in ppt/media/*: {unmatched}"

        return PresentationValidationReport(
            valid=valid,
            slide_count=actual_slides,
            file_size=file_size,
            sha256_hash=file_sha256,
            media_files_verified=len(media_shas),
            matched_media_shas=matched,
            unmatched_media_shas=unmatched,
            error_message=error_message,
            structural_valid=structural_valid,
            content_completeness_valid=content_completeness_valid,
            missing_content_elements=missing_content_elements,
            provenance_valid=provenance_valid,
            typography_valid=typography_valid,
            layout_valid=layout_valid,
            render_back_valid=False,
            automated_nonblank_valid=False,
            automated_bounds_valid=automated_bounds_valid,
            visual_review_status="PENDING",
            demo_ready=False,
            minimum_font_pt_detected=min_font_pt,
            font_size_violations=font_violations,
            layout_anomalies=layout_anomalies,
        )

    @classmethod
    def validate_presentation_visuals(
        cls,
        file_path: Path,
        expected_slide_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes Level 2 Visual Validation using local PowerPoint COM renderer if available.
        Renders back to PNG slides, confirms slide count, resolution, and non-blankness.
        If renderer is unavailable on host, returns VISUAL_VALIDATION = 'NOT_EXECUTED'.
        """
        from cognishift.core.document_processing.office_renderer import render_pptx_slides
        import io
        from PIL import Image
        import numpy as np

        slides, prov = render_pptx_slides(file_path)
        if prov.get("render_status") != "SUCCESS" or not slides:
            return {
                "visual_validation": "NOT_EXECUTED",
                "renderer_status": prov.get("render_status", "UNAVAILABLE"),
                "reason": prov.get("error", "Local PowerPoint COM renderer unavailable on host."),
                "slides_rendered": 0,
                "blank_slides_detected": [],
                "render_back_valid": False,
                "automated_nonblank_valid": False,
            }

        actual_rendered = len(slides)
        blank_slides = []
        dimensions = []

        for s_num, s_bytes in slides:
            try:
                with Image.open(io.BytesIO(s_bytes)) as img:
                    w, h = img.size
                    dimensions.append({"slide": s_num, "width": w, "height": h})
                    # Check for blank / solid white slides
                    gray = img.convert("L")
                    arr = np.array(gray)
                    std_dev = float(np.std(arr))
                    if std_dev < 1.0:  # Pure solid color or completely blank
                        blank_slides.append(s_num)
            except Exception as ie:
                logger.warning(f"Failed verifying image metrics for slide {s_num}: {ie}")

        render_back_valid = (actual_rendered == expected_slide_count if expected_slide_count else actual_rendered > 0)
        automated_nonblank_valid = (len(blank_slides) == 0 and actual_rendered > 0)
        passed = render_back_valid and automated_nonblank_valid

        return {
            "visual_validation": "PASS" if passed else "FAIL",
            "renderer_status": "SUCCESS",
            "renderer_type": prov.get("renderer_type"),
            "slides_rendered": actual_rendered,
            "expected_slides": expected_slide_count,
            "blank_slides_detected": blank_slides,
            "render_back_valid": render_back_valid,
            "automated_nonblank_valid": automated_nonblank_valid,
            "slide_dimensions": dimensions,
            "render_provenance": prov,
        }
