"""
Authoritative Acceptance Gate for CogniShift Artifact Quality V3.
Enforces format- and context-specific applicability rules across 18 disaggregated quality dimensions.
Computes DEMO_READY and ENTERPRISE_READY statuses strictly via conjunctive evaluation.
"""
from typing import Dict, List, Optional, Set

from cognishift.core.artifact_quality.schemas import (
    ArtifactLifecycleState,
    DimensionStatus,
    QualityDimensionReport,
    QualityReport,
)

ACCEPTANCE_GATE_VERSION = "v3.1.0"

DEMO_READY_DIMENSIONS: Set[str] = {
    "structural_valid",
    "content_completeness_valid",
    "provenance_valid",
    "typography_valid",
    "layout_valid",
    "render_back_valid",
    "automated_nonblank_valid",
    "visual_review_status",
}

ENTERPRISE_READY_ADDITIONAL_DIMENSIONS: Set[str] = {
    "semantic_consistency_valid",
    "artifact_context_valid",
    "caption_semantic_valid",
    "source_grounding_valid",
    "sovereignty_claim_valid",
    "page_flow_valid",
    "figure_readability_valid",
    "table_pagination_valid",
    "glyph_rendering_valid",
    "demo_disclosure_valid",
}


def get_applicable_dimensions_for_format(
    artifact_type: str,
    has_figures: bool = False,
    has_multipage_tables: bool = False,
    is_synthetic_demo: bool = False
) -> Set[str]:
    """
    Returns the exact set of required/applicable quality dimensions for an artifact format.
    Non-applicable dimensions are marked NOT_APPLICABLE and do not block acceptance.
    """
    fmt = artifact_type.lower()

    if fmt == "csv":
        dims = {
            "structural_valid",
            "content_completeness_valid",
            "provenance_valid",
            "source_grounding_valid",
            "glyph_rendering_valid",
        }
        if is_synthetic_demo:
            dims.add("demo_disclosure_valid")
        return dims

    elif fmt == "xlsx":
        dims = {
            "structural_valid",
            "content_completeness_valid",
            "provenance_valid",
            "typography_valid",
            "layout_valid",
            "source_grounding_valid",
            "sovereignty_claim_valid",
            "glyph_rendering_valid",
            "semantic_consistency_valid",
        }
        if has_figures:
            dims.update({"figure_readability_valid", "caption_semantic_valid", "artifact_context_valid"})
        if is_synthetic_demo:
            dims.add("demo_disclosure_valid")
        return dims

    elif fmt == "png":
        dims = {
            "structural_valid",
            "content_completeness_valid",
            "provenance_valid",
            "automated_nonblank_valid",
            "figure_readability_valid",
            "semantic_consistency_valid",
            "glyph_rendering_valid",
        }
        if is_synthetic_demo:
            dims.add("demo_disclosure_valid")
        return dims

    elif fmt == "pptx":
        dims = {
            "structural_valid",
            "content_completeness_valid",
            "provenance_valid",
            "typography_valid",
            "layout_valid",
            "render_back_valid",
            "automated_nonblank_valid",
            "visual_review_status",
            "semantic_consistency_valid",
            "source_grounding_valid",
            "sovereignty_claim_valid",
            "glyph_rendering_valid",
        }
        if has_figures:
            dims.update({"artifact_context_valid", "caption_semantic_valid", "figure_readability_valid"})
        if has_multipage_tables:
            dims.add("table_pagination_valid")
        if is_synthetic_demo:
            dims.add("demo_disclosure_valid")
        return dims

    elif fmt in ("pdf", "docx"):
        dims = {
            "structural_valid",
            "content_completeness_valid",
            "provenance_valid",
            "typography_valid",
            "layout_valid",
            "render_back_valid",
            "automated_nonblank_valid",
            "visual_review_status",
            "semantic_consistency_valid",
            "source_grounding_valid",
            "sovereignty_claim_valid",
            "page_flow_valid",
            "glyph_rendering_valid",
        }
        if has_figures:
            dims.update({"artifact_context_valid", "caption_semantic_valid", "figure_readability_valid"})
        if has_multipage_tables:
            dims.add("table_pagination_valid")
        if is_synthetic_demo:
            dims.add("demo_disclosure_valid")
        return dims

    # Default fallback
    return DEMO_READY_DIMENSIONS.union(ENTERPRISE_READY_ADDITIONAL_DIMENSIONS)


def evaluate_acceptance_gate(
    report: QualityReport,
    has_figures: bool = False,
    has_multipage_tables: bool = False,
    is_synthetic_demo: bool = False
) -> QualityReport:
    """
    Authoritative acceptance gate evaluation.
    Only this function is permitted to declare DEMO_READY and ENTERPRISE_READY.
    Evaluates:
    - DEMO_READY: All applicable dimensions in DEMO_READY_DIMENSIONS == PASS
    - ENTERPRISE_READY: All applicable dimensions == PASS
    Fails closed if any applicable dimension is FAIL or NOT_EXECUTED.
    """
    applicable = get_applicable_dimensions_for_format(
        artifact_type=report.artifact_type,
        has_figures=has_figures,
        has_multipage_tables=has_multipage_tables,
        is_synthetic_demo=is_synthetic_demo
    )

    all_known_dimensions = DEMO_READY_DIMENSIONS.union(ENTERPRISE_READY_ADDITIONAL_DIMENSIONS)

    # Mark non-applicable dimensions cleanly
    for dim in all_known_dimensions:
        if dim not in applicable:
            if dim in report.dimensions:
                report.dimensions[dim].status = DimensionStatus.NOT_APPLICABLE
            else:
                report.dimensions[dim] = QualityDimensionReport(
                    dimension_name=dim,
                    status=DimensionStatus.NOT_APPLICABLE,
                    severity="ADVISORY",
                    message="Not applicable for this artifact format and context profile."
                )

    # Evaluate DEMO_READY
    demo_applicable = applicable.intersection(DEMO_READY_DIMENSIONS)
    demo_passes = True
    for dim in demo_applicable:
        dim_rep = report.dimensions.get(dim)
        if not dim_rep or dim_rep.status != DimensionStatus.PASS:
            demo_passes = False
            break

    # Evaluate ENTERPRISE_READY
    enterprise_passes = True
    for dim in applicable:
        dim_rep = report.dimensions.get(dim)
        if not dim_rep or dim_rep.status != DimensionStatus.PASS:
            enterprise_passes = False
            break

    has_any_fail = any(
        dim_rep.status == DimensionStatus.FAIL
        for name, dim_rep in report.dimensions.items()
        if name in applicable
    )
    if has_any_fail:
        demo_passes = False

    report.demo_ready = demo_passes
    report.enterprise_ready = enterprise_passes

    if enterprise_passes:
        report.lifecycle_state = ArtifactLifecycleState.ACCEPTED
    elif has_any_fail or not demo_passes:
        report.lifecycle_state = ArtifactLifecycleState.QA_FAILED
    else:
        report.lifecycle_state = ArtifactLifecycleState.STAGING

    report.validator_versions["acceptance_gate_version"] = ACCEPTANCE_GATE_VERSION
    return report
