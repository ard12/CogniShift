"""Test suite for RCA Evidence Validation and Grounded Finalization Subsystem."""
import pytest
from cognishift.core.rca.schemas import (
    EvidenceRole,
    RCAStatus,
    RCAEvidenceItem,
    RCAEvidenceBundle,
    ChannelExecutionHealth,
)
from cognishift.core.rca.evidence_validation import RCAEvidenceValidator


def test_validate_and_finalize_preserves_supported_root_cause():
    item1 = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=1,
        source_id=10,
        filename="P-101A_Inspection_Report.pdf",
        page_number=3,
        retrieval_channel="text",
        evidence_role=EvidenceRole.INSPECTION,
        content="Suction strainer S-101 was inspected and found 80% blinded with particulate scale.",
        confidence=0.95,
        equipment_ids=["P-101A"]
    )
    item2 = RCAEvidenceItem(
        evidence_id="E2",
        source_type="pdf",
        workspace_id=1,
        source_id=11,
        filename="P-101A_SOP.pdf",
        page_number=4,
        retrieval_channel="text",
        evidence_role=EvidenceRole.SOP_BASELINE,
        content="Suction trip activates at 1.8 bar(g) to protect impeller from cavitation damage.",
        confidence=0.92,
        equipment_ids=["P-101A"]
    )

    bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        required_roles=[EvidenceRole.INSPECTION, EvidenceRole.SOP_BASELINE],
        optional_roles=[],
        evidence_items=[item1, item2],
        missing_required_roles=[],
        contradictions=[],
        source_coverage={"inspection_report": True, "maintenance_sop": True},
        modality_coverage={"text": True, "visual": False, "topology": False, "telemetry": False},
        channel_health=ChannelExecutionHealth(
            requested_channels=["text", "visual", "topology"],
            executed_channels=["text"],
            failed_channels=[]
        )
    )

    model_output = (
        "Based on the evidence [E1] and [E2], here is the analysis:\n\n"
        "## Confirmed Observations\n"
        "- [E1] Suction strainer S-101 was 80% blinded with foreign scale.\n"
        "- [E2] Suction pressure dropped below the 1.8 bar trip limit.\n\n"
        "## Primary Cause\n"
        "Severe suction strainer clogging caused cavitation and low suction pressure trip [E1]."
    )

    validator = RCAEvidenceValidator()
    final_report = validator.validate_and_finalize(
        bundle=bundle,
        model_output=model_output,
        operator_input="Why did P-101A trip? Check the inspection report and SOP."
    )

    assert "## RCA Status" in final_report
    assert "CONFIRMED CAUSE" in final_report or "SUPPORTED LIKELY CAUSE" in final_report
    assert "No root cause is confirmed from the symptom-only" not in final_report
    assert "## Confirmed Observations" in final_report
    assert "## Primary Cause" in final_report
    assert "Severe suction strainer clogging caused cavitation" in final_report
    assert "## Supporting Evidence" in final_report
    assert "[E1]" in final_report
    assert "`P-101A_Inspection_Report.pdf`" in final_report
    assert "## Sources" in final_report
    assert "`P-101A_Inspection_Report.pdf` — Page 3" in final_report


def test_validate_and_finalize_downgrades_unsupported_hypothesis():
    item1 = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=1,
        source_id=10,
        filename="P-101A_SOP.pdf",
        page_number=1,
        retrieval_channel="text",
        evidence_role=EvidenceRole.SOP_BASELINE,
        content="General pump operating guidelines.",
        confidence=0.85,
        equipment_ids=["P-101A"]
    )

    # Missing inspection and vibration required roles
    bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        required_roles=[EvidenceRole.INSPECTION, EvidenceRole.VIBRATION],
        optional_roles=[],
        evidence_items=[item1],
        missing_required_roles=[EvidenceRole.INSPECTION, EvidenceRole.VIBRATION],
        contradictions=[],
        source_coverage={"inspection_report": False, "vibration_log": False},
        modality_coverage={"text": True, "visual": False, "topology": False, "telemetry": False},
        channel_health=ChannelExecutionHealth()
    )

    model_output = (
        "## Primary Cause\n"
        "Impeller fatigue failure destroyed the bearing assembly."
    )

    validator = RCAEvidenceValidator()
    final_report = validator.validate_and_finalize(
        bundle=bundle,
        model_output=model_output,
        operator_input="Investigate P-101A trip."
    )

    assert "PLAUSIBLE HYPOTHESIS" in final_report
    assert "Missing required role evidence: Inspection" in final_report
    assert "Missing required role evidence: Vibration" in final_report


def test_validate_and_finalize_rejects_hallucinated_e_ids():
    item1 = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=1,
        source_id=10,
        filename="K-101_SOP.pdf",
        page_number=2,
        retrieval_channel="text",
        evidence_role=EvidenceRole.SOP_BASELINE,
        content="Discharge temperature alarm limit is 145 C.",
        confidence=0.90,
        equipment_ids=["K-101"]
    )

    bundle = RCAEvidenceBundle(
        asset_ids=["K-101"],
        required_roles=[EvidenceRole.SOP_BASELINE],
        evidence_items=[item1],
        channel_health=ChannelExecutionHealth()
    )

    # Model hallucinates [E99] and [E500]
    model_output = (
        "The compressor tripped because [E99] shows lube oil starvation and [E500] shows seal blowout."
    )

    validator = RCAEvidenceValidator()
    final_report = validator.validate_and_finalize(
        bundle=bundle,
        model_output=model_output,
        operator_input="Check K-101 trip."
    )

    assert "[E99]" not in final_report
    assert "[E500]" not in final_report


def test_validate_and_finalize_ood_asset():
    bundle = RCAEvidenceBundle(
        asset_ids=["K-888"],
        evidence_items=[],
        retrieval_diagnostics={"unregistered_assets": ["K-888"], "ood_triggered": True},
        channel_health=ChannelExecutionHealth()
    )

    validator = RCAEvidenceValidator()
    final_report = validator.validate_and_finalize(
        bundle=bundle,
        model_output="",
        operator_input="Why did compressor K-888 trip?"
    )

    assert "ASSET_NOT_FOUND" in final_report
    assert "Equipment `K-888` is not registered" in final_report
    assert "None (Asset Not Found)" in final_report


def test_validate_and_finalize_empty_bundle():
    bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        evidence_items=[],
        channel_health=ChannelExecutionHealth()
    )

    validator = RCAEvidenceValidator()
    final_report = validator.validate_and_finalize(
        bundle=bundle,
        model_output="",
        operator_input="Why did P-101A trip?"
    )

    assert "INSUFFICIENT_EVIDENCE" in final_report
    assert "No root cause is confirmed from the symptom-only information provided" in final_report
