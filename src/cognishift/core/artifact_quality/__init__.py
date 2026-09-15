"""
CogniShift Artifact Quality V3 Package.
Authoritative orchestrator, schemas, compatibility validators, planners, and acceptance gates.
"""
from cognishift.core.artifact_quality.schemas import (
    DimensionStatus,
    VisualPurpose,
    PhysicalDimension,
    MeasuredQuantity,
    TimeWindow,
    EvidenceReference,
    StandardClaim,
    ArtifactLifecycleState,
    ArtifactSemanticMetadata,
    GroundedArtifactContext,
    CalloutType,
    CalloutBlock,
    DocumentType,
    QualityDimensionReport,
    QualityReport,
)
from cognishift.core.artifact_quality.compatibility_validator import (
    validate_artifact_context_compatibility,
    validate_figure_caption,
    validate_sovereignty_wording,
    validate_demo_disclosure,
    validate_standards_grounding,
    validate_signatory_authenticity,
)
from cognishift.core.artifact_quality.flow_validator import (
    validate_page_flow,
    validate_table_pagination,
    validate_figure_readability,
    validate_glyph_rendering,
)
from cognishift.core.artifact_quality.acceptance_gate import (
    evaluate_acceptance_gate,
    get_applicable_dimensions_for_format,
)
from cognishift.core.artifact_quality.report_planner import (
    TechnicalReportPlanner,
    TechnicalReportSpec,
)
from cognishift.core.artifact_quality.sop_planner import (
    SOPPlanner,
    SOPSpec,
)
from cognishift.core.artifact_quality.service import ArtifactGenerationService

__all__ = [
    "DimensionStatus",
    "VisualPurpose",
    "PhysicalDimension",
    "MeasuredQuantity",
    "TimeWindow",
    "EvidenceReference",
    "StandardClaim",
    "ArtifactLifecycleState",
    "ArtifactSemanticMetadata",
    "GroundedArtifactContext",
    "CalloutType",
    "CalloutBlock",
    "DocumentType",
    "QualityDimensionReport",
    "QualityReport",
    "validate_artifact_context_compatibility",
    "validate_figure_caption",
    "validate_sovereignty_wording",
    "validate_demo_disclosure",
    "validate_standards_grounding",
    "validate_signatory_authenticity",
    "validate_page_flow",
    "validate_table_pagination",
    "validate_figure_readability",
    "validate_glyph_rendering",
    "evaluate_acceptance_gate",
    "get_applicable_dimensions_for_format",
    "TechnicalReportPlanner",
    "TechnicalReportSpec",
    "SOPPlanner",
    "SOPSpec",
    "ArtifactGenerationService",
]
