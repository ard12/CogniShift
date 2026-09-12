"""Deterministic RCA Evaluation Policy and Tool Failure Severity."""
from enum import Enum
from typing import List, Optional
from cognishift.core.rca.schemas import RCAStatus, RCAEvidenceItem, EvidenceRole


class ToolFailureSeverity(str, Enum):
    REQUIRED_EVIDENCE_FAILURE = "REQUIRED_EVIDENCE_FAILURE"
    OPTIONAL_ENRICHMENT_FAILURE = "OPTIONAL_ENRICHMENT_FAILURE"
    HIGH_RISK_OPERATION_FAILURE = "HIGH_RISK_OPERATION_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


def classify_tool_failure_severity(
    tool_name: str,
    is_rca_mode: bool = False,
    is_explicitly_required: bool = False
) -> ToolFailureSeverity:
    """
    Categorizes the impact of a tool call failure.
    Ensures optional diagnostic checks in RCA never abort an otherwise grounded analysis.
    """
    high_risk_tools = {"emergency_pressure_relief", "restart_component", "restart_service"}
    if tool_name in high_risk_tools:
        return ToolFailureSeverity.HIGH_RISK_OPERATION_FAILURE

    if is_explicitly_required:
        return ToolFailureSeverity.REQUIRED_EVIDENCE_FAILURE

    if is_rca_mode and tool_name in ("check_temperature", "check_pressure", "check_network", "run_diagnostic", "check_interlock_status", "file_read"):
        return ToolFailureSeverity.OPTIONAL_ENRICHMENT_FAILURE

    return ToolFailureSeverity.INFRASTRUCTURE_FAILURE


def determine_rca_status(
    required_roles_satisfied: bool,
    supporting_items: List[RCAEvidenceItem],
    contradictions: Optional[List[str]] = None,
    has_causal_chronology: bool = False,
    operator_symptoms_only: bool = False,
    has_missing_critical: bool = False
) -> RCAStatus:
    """
    Deterministic decision rules for Root Cause Analysis status:
    - CONFIRMED_CAUSE: strong direct evidence, physical telemetry/inspection, causal chronology, no material contradictions, required coverage complete.
    - SUPPORTED_LIKELY_CAUSE: multiple independent evidence sources, required coverage complete, plausible causal chain, no stronger competing explanation.
    - PLAUSIBLE_HYPOTHESIS: some support, important or critical evidence still missing.
    - CONTRADICTORY_EVIDENCE: evidence materially conflicts.
    - INSUFFICIENT_EVIDENCE: required evidence absent or too weak, or only symptom-only operator description.
    """
    if operator_symptoms_only and not supporting_items:
        return RCAStatus.INSUFFICIENT_EVIDENCE

    if contradictions and len(contradictions) > 0:
        return RCAStatus.CONTRADICTORY_EVIDENCE

    if not supporting_items:
        return RCAStatus.INSUFFICIENT_EVIDENCE

    # Count distinct source documents / modalities
    distinct_sources = {item.filename for item in supporting_items if item.filename}
    distinct_roles = {item.evidence_role for item in supporting_items}

    # Physical telemetry / measurement check
    physical_roles = {
        EvidenceRole.PRESSURE,
        EvidenceRole.TEMPERATURE,
        EvidenceRole.VIBRATION,
        EvidenceRole.LIVE_TELEMETRY,
        EvidenceRole.HISTORICAL_TELEMETRY,
        EvidenceRole.INSPECTION
    }
    has_physical_measurement = bool(distinct_roles & physical_roles)

    # Empirical / Incident check: baseline SOPs alone without incident data cannot prove a failure hypothesis
    incident_roles = {
        EvidenceRole.INCIDENT_CHRONOLOGY,
        EvidenceRole.INSPECTION,
        EvidenceRole.PRESSURE,
        EvidenceRole.TEMPERATURE,
        EvidenceRole.VIBRATION,
        EvidenceRole.LIVE_TELEMETRY,
        EvidenceRole.HISTORICAL_TELEMETRY,
        EvidenceRole.P_AND_ID,
    }
    has_incident_evidence = bool(distinct_roles & incident_roles)
    if not has_incident_evidence:
        return RCAStatus.INSUFFICIENT_EVIDENCE

    # CRITICAL EVIDENCE GATE:
    # If required evidence roles or critical evidence are missing, status cannot exceed PLAUSIBLE_HYPOTHESIS
    if not required_roles_satisfied or has_missing_critical:
        if len(supporting_items) >= 1:
            return RCAStatus.PLAUSIBLE_HYPOTHESIS
        return RCAStatus.INSUFFICIENT_EVIDENCE

    # If required evidence coverage is complete and multiple sources corroborate
    if len(distinct_sources) >= 2:
        if (has_causal_chronology or (EvidenceRole.INCIDENT_CHRONOLOGY in distinct_roles and EvidenceRole.SOP_BASELINE in distinct_roles)) and has_physical_measurement:
            return RCAStatus.CONFIRMED_CAUSE
        return RCAStatus.SUPPORTED_LIKELY_CAUSE

    if len(supporting_items) >= 1:
        return RCAStatus.PLAUSIBLE_HYPOTHESIS

    return RCAStatus.INSUFFICIENT_EVIDENCE
