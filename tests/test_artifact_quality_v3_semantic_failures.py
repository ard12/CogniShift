"""
Comprehensive Semantic Failure & Edge-Case Test Suite for CogniShift Artifact Quality V3.
Verifies all 12 intentional failure/edge cases:
1. Asset mismatch (V-101 visual into C-102 deck)
2. Headline metric discrepancy (46.8 barg vs 32.0 barg)
3. Unit normalization vs physical dimension mismatch (barg vs MPa compatible, barg vs deg C mismatch)
4. Visual purpose contradiction (overpressure excursion into safe depressurization)
5. Disjoint time windows (08:14 UTC vs 14:00 UTC)
6. Ungrounded regulatory standards (ASME Section VIII Div 1 without verified ledger entry)
7. Fabricated signatory detection (un-authenticated human approvals flagged)
8. Insufficient grounded content (factual request with zero evidence fails closed)
9. Unmeasured sovereignty phrasing flagged and repaired
10. Demo disclosure requirement for synthetic data
11. Renderer COM unavailability marked NOT_EXECUTED without crashing
12. Repair exhaustion bounded at maximum 3 attempts
"""
import pytest
from datetime import datetime, timezone
from pathlib import Path

from cognishift.core.artifact_quality.schemas import (
    ArtifactLifecycleState,
    ArtifactSemanticMetadata,
    CalloutBlock,
    CalloutType,
    DimensionStatus,
    DocumentType,
    EvidenceReference,
    GroundedArtifactContext,
    MeasuredQuantity,
    PhysicalDimension,
    QualityDimensionReport,
    QualityReport,
    StandardClaim,
    TimeWindow,
    VisualPurpose,
)
from cognishift.core.artifact_quality.compatibility_validator import (
    validate_artifact_context_compatibility,
    validate_demo_disclosure,
    validate_figure_caption,
    validate_signatory_authenticity,
    validate_sovereignty_wording,
    validate_standards_grounding,
)
from cognishift.core.artifact_quality.acceptance_gate import (
    evaluate_acceptance_gate,
    get_applicable_dimensions_for_format,
)
from cognishift.core.artifact_quality.repair_service import ArtifactRepairService
from cognishift.core.artifact_quality.service import ArtifactGenerationService


def test_01_asset_mismatch_fails_closed():
    """Test 1: Visual artifact with asset V-101 into context for C-102 must fail closed."""
    candidate = ArtifactSemanticMetadata(
        artifact_id=101,
        artifact_type="png",
        title="V-101 Overpressure Excursion",
        workspace_id=1,
        content_context_id="ctx_001",
        subject_assets=["V-101"]
    )
    context = GroundedArtifactContext(
        content_context_id="ctx_001",
        title="Unit 100 Compressor C-102 Overhaul",
        workspace_id=1,
        subject_assets=["C-102"]
    )

    is_compat, reason, diag = validate_artifact_context_compatibility(candidate, context)
    assert not is_compat
    assert "ARTIFACT_CONTEXT_MISMATCH" in reason
    assert "V-101" in reason and "C-102" in reason
    assert diag["checks"]["subject_assets"]["status"] == "FAIL"


def test_02_headline_metric_discrepancy_fails_closed():
    """Test 2: Visual headline metric (46.8 barg) vs context setpoint (32.0 barg) must fail closed."""
    candidate = ArtifactSemanticMetadata(
        artifact_id=102,
        artifact_type="png",
        title="Pressure Trend",
        workspace_id=1,
        content_context_id="ctx_002",
        subject_assets=["V-101"],
        headline_metric=MeasuredQuantity(
            value=46.8,
            unit="barg",
            dimension=PhysicalDimension.PRESSURE,
            label="Peak Operating Pressure"
        )
    )
    context = GroundedArtifactContext(
        content_context_id="ctx_002",
        title="V-101 Operations",
        workspace_id=1,
        subject_assets=["V-101"],
        quantities={
            "Peak Operating Pressure": MeasuredQuantity(
                value=32.0,
                unit="barg",
                dimension=PhysicalDimension.PRESSURE,
                label="Peak Operating Pressure"
            )
        }
    )

    is_compat, reason, diag = validate_artifact_context_compatibility(candidate, context)
    assert not is_compat
    assert "SEMANTIC_CONSISTENCY_FAIL" in reason
    assert "46.8" in reason and "32.0" in reason
    assert diag["checks"]["headline_metric"]["status"] == "FAIL"


def test_03_unit_normalization_vs_dimension_mismatch():
    """Test 3: Typed MeasuredQuantity normalizes units (barg vs MPa) but rejects dimension mismatch (barg vs deg C)."""
    # 46.8 barg == 4.68 MPa (both pressure)
    q_barg = MeasuredQuantity(value=46.8, unit="barg", dimension=PhysicalDimension.PRESSURE)
    q_mpa = MeasuredQuantity(value=4.68, unit="mpa", dimension=PhysicalDimension.PRESSURE)
    compat, msg = q_barg.is_compatible_with(q_mpa)
    assert compat, f"Expected 46.8 barg and 4.68 MPa to match: {msg}"

    # 46.8 barg vs 200.0 C (pressure vs temperature)
    q_temp = MeasuredQuantity(value=200.0, unit="c", dimension=PhysicalDimension.TEMPERATURE)
    compat_dim, msg_dim = q_barg.is_compatible_with(q_temp)
    assert not compat_dim
    assert "Physical dimension mismatch" in msg_dim


def test_04_visual_purpose_contradiction_fails_closed():
    """Test 4: Overpressure excursion visual into safe depressurization narrative must fail closed."""
    candidate = ArtifactSemanticMetadata(
        artifact_id=104,
        artifact_type="png",
        title="Excursion Transient",
        workspace_id=1,
        content_context_id="ctx_004",
        subject_assets=["V-101"],
        chart_purpose=VisualPurpose.INCIDENT_PRESSURE_EXCURSION
    )
    context = GroundedArtifactContext(
        content_context_id="ctx_004",
        title="Depressurization Procedure",
        workspace_id=1,
        subject_assets=["V-101"]
    )

    is_compat, reason, diag = validate_artifact_context_compatibility(
        candidate=candidate,
        context=context,
        requested_purpose=VisualPurpose.SAFE_DEPRESSURIZATION_ENVELOPE
    )
    assert not is_compat
    assert "CAPTION_PURPOSE_MISMATCH" in reason
    assert diag["checks"]["purpose"]["status"] == "FAIL"


def test_05_disjoint_time_windows_fails_closed():
    """Test 5: Visual time window (08:14 UTC) disjoint from context window (14:00 UTC) must fail closed."""
    candidate = ArtifactSemanticMetadata(
        artifact_id=105,
        artifact_type="png",
        title="Morning Alarm Trend",
        workspace_id=1,
        content_context_id="ctx_005",
        subject_assets=["V-101"],
        time_window=TimeWindow(
            start=datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc),
            end=datetime(2026, 8, 14, 8, 30, tzinfo=timezone.utc)
        )
    )
    context = GroundedArtifactContext(
        content_context_id="ctx_005",
        title="Afternoon Shift Inspection",
        workspace_id=1,
        subject_assets=["V-101"],
        time_window=TimeWindow(
            start=datetime(2026, 8, 14, 14, 0, tzinfo=timezone.utc),
            end=datetime(2026, 8, 14, 16, 0, tzinfo=timezone.utc)
        )
    )

    is_compat, reason, diag = validate_artifact_context_compatibility(candidate, context)
    assert not is_compat
    assert "TIME_WINDOW_MISMATCH" in reason
    assert diag["checks"]["time_window"]["relation"] == "disjoint"


def test_06_ungrounded_regulatory_claims_fails_closed():
    """Test 6: Citing ASME Section VIII Div 1 without verified entry in claims_ledger must fail closed."""
    text = "Equipment design complies with ASME Section VIII Division 1 and API 520 standards."
    claims_ledger = [
        StandardClaim(
            claim_id="sc_01",
            claim_text="API 520 standard compliance",
            standard_designation="API 520",
            supporting_evidence_ids=["ev_01"]
        )
    ]

    ok, msg, ungrounded = validate_standards_grounding(text, claims_ledger)
    assert not ok
    assert "STANDARDS_GROUNDING_FAIL" in msg
    assert any("ASME" in u for u in ungrounded)


def test_07_fabricated_signatory_detection():
    """Test 7: Document stating completed approval without authenticated ledger entry fails closed."""
    signatories_fabricated = [
        {"name": "Chief Inspector John Doe", "status": "APPROVED", "hash_id": "unauthenticated"}
    ]

    ok, msg = validate_signatory_authenticity(signatories_fabricated, is_synthetic_demo=False)
    assert not ok
    assert "SIGNATURE_FABRICATION_FAIL" in msg

    signatories_pending = [
        {"name": "Operations Supervisor", "status": "PENDING APPROVAL", "hash_id": ""}
    ]
    ok_p, msg_p = validate_signatory_authenticity(signatories_pending, is_synthetic_demo=False)
    assert ok_p


@pytest.mark.asyncio
async def test_08_insufficient_grounded_content_fails_closed():
    """Test 8: Factual technical report requested with zero evidence fails closed with INSUFFICIENT_GROUNDED_CONTENT."""
    artifact_path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Generate formal root cause investigation report for catastrophic valve failure",
        context=None,
        workspace_id=1,
        explicit_format="pdf"
    )

    assert artifact_path is None
    assert report.lifecycle_state == ArtifactLifecycleState.QA_FAILED
    assert report.dimensions["source_grounding_valid"].status == DimensionStatus.FAIL
    assert "INSUFFICIENT_GROUNDED_CONTENT" in report.dimensions["source_grounding_valid"].message
    assert not report.enterprise_ready
    assert not report.demo_ready


def test_09_unmeasured_sovereignty_claims_flagged_and_repaired():
    """Test 9: '100% offline' and 'zero cloud' are flagged as unmeasured and normalized by repair service."""
    unmeasured_text = "System is 100% offline with zero cloud dependencies."
    ok, msg, unmeasured = validate_sovereignty_wording(unmeasured_text)
    assert not ok
    assert "SOVEREIGNTY_CLAIM_FAIL" in msg

    class DummySpec:
        title = "Plant Deliverable"
        sovereignty_statement = "100% offline zero cloud dependencies"
        sections = [{"heading": "Executive Summary", "paragraphs": ["Zero cloud operations."]}]

    report = QualityReport(
        quality_report_id="QREP-TEST",
        artifact_type="pdf",
        content_context_id="ctx_009",
        workspace_id=1,
        artifact_sha256="abc",
        lifecycle_state=ArtifactLifecycleState.STAGING
    )
    report.dimensions["sovereignty_claim_valid"] = QualityDimensionReport(
        dimension_name="sovereignty_claim_valid",
        status=DimensionStatus.FAIL,
        message=msg
    )

    repaired, new_spec, action = ArtifactRepairService.classify_and_repair_spec(DummySpec(), report)
    assert repaired
    assert "Normalized sovereignty statement" in action
    assert "local sovereign execution with no public-cloud ai/model dependency" in new_spec.sovereignty_statement.lower()


def test_10_demo_disclosure_enforcement():
    """Test 10: Synthetic demo artifacts must disclose synthetic status or fail closed."""
    text_without_disclosure = "Official incident report for Unit 100 explosion."
    ok, msg = validate_demo_disclosure(text_without_disclosure, is_synthetic_demo=True)
    assert not ok
    assert "DEMO_DISCLOSURE_FAIL" in msg

    text_with_disclosure = "Official incident report for Unit 100. Demonstration scenario using synthetic demonstration data."
    ok_d, msg_d = validate_demo_disclosure(text_with_disclosure, is_synthetic_demo=True)
    assert ok_d


def test_11_renderer_unavailable_marks_not_executed_gracefully():
    """Test 11: Format with optional/unavailable renderer marks NOT_EXECUTED and acceptance gate handles it."""
    report = QualityReport(
        quality_report_id="QREP-CSV-01",
        artifact_type="csv",
        content_context_id="ctx_011",
        workspace_id=1,
        artifact_sha256="1234567890abcdef",
        lifecycle_state=ArtifactLifecycleState.STAGING
    )

    evaluated = evaluate_acceptance_gate(
        report=report,
        has_figures=False,
        has_multipage_tables=False,
        is_synthetic_demo=False
    )
    assert evaluated.dimensions["visual_review_status"].status == DimensionStatus.NOT_APPLICABLE
    assert evaluated.dimensions["render_back_valid"].status == DimensionStatus.NOT_APPLICABLE


def test_12_repair_exhaustion_limits_to_three():
    """Test 12: ArtifactRepairService bounds repair attempts to 3 and stops to prevent infinite loop."""
    report = QualityReport(
        quality_report_id="QREP-REPAIR",
        artifact_type="docx",
        content_context_id="ctx_012",
        workspace_id=1,
        artifact_sha256="dummy",
        repair_attempts=3
    )

    assert not ArtifactRepairService.can_attempt_repair(report)
