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
    operator_symptoms_only: bool = False
) -> RCAStatus:
    """
    Deterministic decision rules for Root Cause Analysis status:
    - CONFIRMED_CAUSE: strong direct evidence, causal chronology, no material contradictions, required coverage complete.
    - SUPPORTED_LIKELY_CAUSE: multiple independent evidence sources, plausible causal chain, no stronger competing explanation.
    - PLAUSIBLE_HYPOTHESIS: some support, important evidence still missing.
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
    distinct_sources = set()
    distinct_roles = set()
    for item in supporting_items:
        distinct_sources.add(item.filename)
        distinct_roles.add(item.evidence_role)

    # If required evidence coverage is complete and multiple sources corroborate
    if required_roles_satisfied and len(distinct_sources) >= 2:
        if has_causal_chronology or (EvidenceRole.INCIDENT_CHRONOLOGY in distinct_roles and EvidenceRole.SOP_BASELINE in distinct_roles):
            return RCAStatus.CONFIRMED_CAUSE
        return RCAStatus.SUPPORTED_LIKELY_CAUSE

    if len(supporting_items) >= 1:
        return RCAStatus.PLAUSIBLE_HYPOTHESIS

    return RCAStatus.INSUFFICIENT_EVIDENCE
