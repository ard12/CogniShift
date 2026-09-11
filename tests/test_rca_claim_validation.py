"""
Unit tests for non-circular cause validation, critical evidence gating,
and claim-level support validation in RCA.
"""
import pytest
from cognishift.core.rca.schemas import (
    RCAStatus,
    PrimaryCauseCode,
    EvidenceRole,
    EvidenceCriticality,
    RCAEvidenceItem,
    RCAEvidenceBundle
)
from cognishift.core.rca.policy import determine_rca_status
from cognishift.core.rca.evidence_validation import (
    determine_primary_cause_code,
    RCAEvidenceValidator
)


def test_determine_primary_cause_code_non_circular():
    """Verify that cause code determination uses physical evidence facts and not hardcoded asset names."""
    # Test 1: Brand new pump P-999 exhibiting suction starvation facts
    bundle_pump = RCAEvidenceBundle(
        asset_ids=["P-999"],
        evidence_items=[
            RCAEvidenceItem(
                evidence_id="E1",
                source_type="pdf",
                workspace_id=1,
                filename="p999_log.pdf",
                page_number=1,
                retrieval_channel="text",
                evidence_role=EvidenceRole.PRESSURE,
                content="Suction pressure dropped below NPSH margin. Strainer debris accumulation caused pump cavitation."
            )
        ]
    )
    code_pump = determine_primary_cause_code(
        status=RCAStatus.SUPPORTED_LIKELY_CAUSE,
        primary_cause_text="Pump suction starvation and cavitation due to clogged suction strainer",
        observations=["Suction pressure was 0.8 bar against 1.5 bar threshold"],
        bundle=bundle_pump
    )
    assert code_pump == PrimaryCauseCode.SUCTION_STARVATION_CAVITATION

    # Test 2: Compressor C-777 exhibiting journal bearing high temperature
    bundle_comp = RCAEvidenceBundle(
        asset_ids=["C-777"],
        evidence_items=[
            RCAEvidenceItem(
                evidence_id="E1",
                source_type="pdf",
                workspace_id=1,
                filename="compressor_log.pdf",
                page_number=4,
                retrieval_channel="text",
                evidence_role=EvidenceRole.TEMPERATURE,
                content="Journal bearing drive-end temperature exceeded 112 deg C. Bearing overheat initiated trip."
            )
        ]
    )
    code_comp = determine_primary_cause_code(
        status=RCAStatus.SUPPORTED_LIKELY_CAUSE,
        primary_cause_text="Compressor bearing overheat from journal wear",
        observations=["TT-901 exceeded high alarm"],
        bundle=bundle_comp
    )
    assert code_comp == PrimaryCauseCode.BEARING_OVERHEAT


def test_determine_primary_cause_code_validates_model_proposal():
    """Verify that model-proposed cause code is verified against physical facts in the bundle."""
    bundle = RCAEvidenceBundle(
        asset_ids=["V-400"],
        evidence_items=[
            RCAEvidenceItem(
                evidence_id="E1",
                source_type="pdf",
                workspace_id=1,
                filename="valve_sheet.pdf",
                page_number=2,
                retrieval_channel="text",
                evidence_role=EvidenceRole.INSPECTION,
                content="Valve stem binding observed during stroke test; actuator hysteresis exceeded 15%."
            )
        ]
    )
    # Valid model proposal matching evidence facts
    code_valid = determine_primary_cause_code(
        status=RCAStatus.SUPPORTED_LIKELY_CAUSE,
        primary_cause_text="Valve stem binding prevented full closure",
        observations=["Stroke test failed"],
        bundle=bundle,
        parsed_code="VALVE_STEM_BINDING"
    )
    assert code_valid == PrimaryCauseCode.VALVE_STEM_BINDING


def test_critical_evidence_gate_caps_status_at_hypothesis():
    """Verify that if REQUIRED_CRITICAL evidence is missing, status is capped at PLAUSIBLE_HYPOTHESIS."""
    item1 = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=1,
        filename="doc1.pdf",
        page_number=1,
        retrieval_channel="text",
        evidence_role=EvidenceRole.INCIDENT_CHRONOLOGY,
        content="Pump trip occurred at 14:00"
    )
    item2 = RCAEvidenceItem(
        evidence_id="E2",
        source_type="pdf",
        workspace_id=1,
        filename="doc2.pdf",
        page_number=3,
        retrieval_channel="text",
        evidence_role=EvidenceRole.SOP_BASELINE,
        content="SOP requires suction pressure above 1.5 bar"
    )

    # Missing critical vibration or telemetry data: required_roles_satisfied is False
    status_missing = determine_rca_status(
        required_roles_satisfied=False,
        supporting_items=[item1, item2],
        has_causal_chronology=True,
        has_missing_critical=True
    )
    assert status_missing == RCAStatus.PLAUSIBLE_HYPOTHESIS


def test_observation_snapping_does_not_invent_citations():
    """Verify that ungrounded observations are NOT falsely attributed to supported_items[0]."""
    validator = RCAEvidenceValidator()
    bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        evidence_items=[
            RCAEvidenceItem(
                evidence_id="E1",
                source_type="pdf",
                workspace_id=1,
                filename="pumps_manual.pdf",
                page_number=16,
                retrieval_channel="text",
                evidence_role=EvidenceRole.PRESSURE,
                content="Suction pressure dropped to 0.4 bar causing cavitation."
            )
        ]
    )

    # Model returns two observations: one grounded, one hallucinated/unrelated
    model_output = (
        "## Confirmed Observations\n"
        "- Suction pressure dropped to 0.4 bar causing cavitation [E1]\n"
        "- The control room operator spilled coffee on the console\n\n"
        "## Primary Cause\n"
        "Suction starvation cavitation\n"
    )

    final_report = validator.validate_and_finalize(bundle, model_output, "RCA for P-101A")

    # The grounded observation has citation
    assert "[E1]" in final_report
    assert "[pumps_manual.pdf | Page 16]" in final_report

    # The unrelated observation MUST NOT have [E1] or [pumps_manual.pdf] attached to it!
    for line in final_report.splitlines():
        if "coffee on the console" in line:
            assert "[E1]" not in line
            assert "pumps_manual.pdf" not in line
