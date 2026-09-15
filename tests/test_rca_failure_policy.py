"""Test suite for RCA Tool Failure Severity Classification and RCA Status Policy."""
import pytest
from cognishift.core.rca.schemas import EvidenceRole, RCAStatus, RCAEvidenceItem
from cognishift.core.rca.policy import (
    ToolFailureSeverity,
    classify_tool_failure_severity,
    determine_rca_status
)


def test_classify_tool_failure_severity_high_risk():
    assert classify_tool_failure_severity("restart_component") == ToolFailureSeverity.HIGH_RISK_OPERATION_FAILURE
    assert classify_tool_failure_severity("emergency_pressure_relief") == ToolFailureSeverity.HIGH_RISK_OPERATION_FAILURE
    assert classify_tool_failure_severity("restart_service") == ToolFailureSeverity.HIGH_RISK_OPERATION_FAILURE


def test_classify_tool_failure_severity_rca_optional():
    assert classify_tool_failure_severity("check_temperature", is_rca_mode=True) == ToolFailureSeverity.OPTIONAL_ENRICHMENT_FAILURE
    assert classify_tool_failure_severity("check_pressure", is_rca_mode=True) == ToolFailureSeverity.OPTIONAL_ENRICHMENT_FAILURE
    assert classify_tool_failure_severity("run_diagnostic", is_rca_mode=True) == ToolFailureSeverity.OPTIONAL_ENRICHMENT_FAILURE
    assert classify_tool_failure_severity("file_read", is_rca_mode=True) == ToolFailureSeverity.OPTIONAL_ENRICHMENT_FAILURE


def test_classify_tool_failure_severity_explicitly_required():
    assert classify_tool_failure_severity("check_temperature", is_rca_mode=True, is_explicitly_required=True) == ToolFailureSeverity.REQUIRED_EVIDENCE_FAILURE


def test_determine_rca_status_confirmed_cause():
    item1 = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=1,
        filename="P-101A_Inspection.pdf",
        page_number=2,
        retrieval_channel="text",
        evidence_role=EvidenceRole.INSPECTION,
        content="Impeller eye severely blocked by weld slag.",
        confidence=0.95
    )
    item2 = RCAEvidenceItem(
        evidence_id="E2",
        source_type="pdf",
        workspace_id=1,
        filename="P-101A_SOP.pdf",
        page_number=5,
        retrieval_channel="text",
        evidence_role=EvidenceRole.SOP_BASELINE,
        content="Normal suction delta P limit exceeded.",
        confidence=0.90
    )

    status = determine_rca_status(
        required_roles_satisfied=True,
        supporting_items=[item1, item2],
        contradictions=[],
        has_causal_chronology=True,
        operator_symptoms_only=False
    )
    assert status == RCAStatus.CONFIRMED_CAUSE


def test_determine_rca_status_contradictory_evidence():
    item1 = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=1,
        filename="Report1.pdf",
        retrieval_channel="text",
        evidence_role=EvidenceRole.INSPECTION,
        content="Bearing was intact with zero wear.",
        confidence=0.90
    )
    status = determine_rca_status(
        required_roles_satisfied=True,
        supporting_items=[item1],
        contradictions=["Vibration log indicates severe catastrophic bearing disintegration"],
        operator_symptoms_only=False
    )
    assert status == RCAStatus.CONTRADICTORY_EVIDENCE


def test_determine_rca_status_insufficient_evidence():
    status = determine_rca_status(
        required_roles_satisfied=False,
        supporting_items=[],
        operator_symptoms_only=True
    )
    assert status == RCAStatus.INSUFFICIENT_EVIDENCE
