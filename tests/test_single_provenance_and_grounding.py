"""
Unit tests for Single-Provenance Pipeline, Evidence Sufficiency Gate,
Deterministic SCADA Anomaly Grounding, and DeepSeek Thinking Hygiene.
"""
import pytest
from cognishift.core.document_insights import (
    validate_scada_anomaly_prose,
    build_authoritative_anomaly_response,
    StructuredAnomalyResult
)
from cognishift.core.engine import (
    validate_evidence_sufficiency,
    extract_and_strip_thinking,
    GoalContract
)
from cognishift.core.conversation_context import ResolvedSource


def test_evidence_sufficiency_rejects_substring_distractors():
    """Verify that words like 'independent', 'rendered', 'vendor' do not trigger false corrosion evidence."""
    query = "What is the remaining corrosion life of P-101A according to the latest inspection report?"
    distractor_context = (
        "The independent vendor rendered services for pipeline maintenance and approved the electrical panel. "
        "All work was completed according to vendor specifications."
    )
    is_suff, reason = validate_evidence_sufficiency(query, distractor_context)
    assert is_suff is False
    assert "corrosion" in reason.lower() or "inspection" in reason.lower()


def test_evidence_sufficiency_accepts_authentic_corrosion_evidence():
    """Verify that authentic corrosion/NDE evidence passes sufficiency validation."""
    query = "What is the remaining corrosion life of P-101A?"
    valid_context = (
        "[Inspection Report | Page 4]\n"
        "NDE ultrasonic thickness inspection on P-101A indicated remaining wall thickness 8.4mm, "
        "corrosion rate 0.12 mm/yr, remaining corrosion life 14.2 years."
    )
    is_suff, reason = validate_evidence_sufficiency(query, valid_context)
    assert is_suff is True


def test_deepseek_thinking_hygiene():
    """Verify that <think>...</think> blocks are stripped from model output."""
    raw_output = (
        "<think>\n"
        "The operator is asking for the status of pump P-101A.\n"
        "Let me check the latest readings and evaluate temperature limits.\n"
        "</think>\n"
        "Pump P-101A is currently operating within nominal baseline parameters (Discharge Pressure: 142.5 PSI)."
    )
    cleaned, reasoning_detected, reasoning_chars = extract_and_strip_thinking(raw_output)
    assert "<think>" not in cleaned
    assert "</think>" not in cleaned
    assert "Pump P-101A is currently operating" in cleaned
    assert reasoning_detected is True
    assert reasoning_chars > 0


def test_scada_anomaly_prose_validation_accepts_grounded_prose():
    """Verify that grounded model prose referencing frozen anomaly facts passes validation."""
    anomaly = {
        "has_anomaly": True,
        "row_index": 523,
        "timestamp": "2026-09-06 17:10:00",
        "component_id": "P-101A",
        "status_indicator": "CRITICAL_SPIKE",
        "valve_status": "CLOSED",
        "valve_column": "sv402_relief_valve_status",
        "spiked_columns": [
            {"column": "discharge_pressure_psi", "value": 537.4, "before": 142.1, "after": 142.3, "pct_change_vs_before": 278.18},
            {"column": "vibration_rms_mm_s", "value": 12.34, "before": 1.45, "after": 1.46, "pct_change_vs_before": 751.03}
        ],
        "analysis_scope": {"total_rows_scanned": 576, "complete": True}
    }
    prose = (
        "On 2026-09-06 17:10:00, pump P-101A experienced a critical pressure excursion to 537.4 PSI "
        "while relief valve SV-402 was closed. Vibration spiked to 12.34 mm/s."
    )
    is_valid, validated_text = validate_scada_anomaly_prose(prose, anomaly, "scada_log.xlsx")
    assert is_valid is True
    assert validated_text == prose


def test_scada_anomaly_prose_validation_rejects_and_overrides_contradictory_prose():
    """Verify that prose claiming wrong year (2023) or contradictory valve state (OPEN) is replaced deterministically."""
    anomaly = {
        "has_anomaly": True,
        "row_index": 523,
        "timestamp": "2026-09-06 17:10:00",
        "component_id": "P-101A",
        "status_indicator": "CRITICAL_SPIKE",
        "valve_status": "CLOSED",
        "valve_column": "sv402_relief_valve_status",
        "spiked_columns": [
            {"column": "discharge_pressure_psi", "value": 537.4, "before": 142.1, "after": 142.3, "pct_change_vs_before": 278.18}
        ],
        "analysis_scope": {"total_rows_scanned": 576, "complete": True}
    }
    # Hallucinated 2023 date and claimed valve opened
    hallucinated_prose = "In October 2023, the pump tripped and the relief valve was opened."
    is_valid, validated_text = validate_scada_anomaly_prose(hallucinated_prose, anomaly, "MRPL_Crude_Distillation_Unit_Telemetry_Sept2026.xlsx")
    assert is_valid is False
    # Must contain deterministic authoritative report
    assert "Authoritative SCADA Anomaly Detection Report" in validated_text
    assert "2026-09-06 17:10:00" in validated_text
    assert "CLOSED" in validated_text
    assert "537.4" in validated_text


def test_goal_contract_evaluation():
    """Verify GoalContract evaluates required fields accurately."""
    contract = GoalContract(
        required_fields=["revenue_latest", "ebitda_latest", "pat_latest", "revenue_yoy_pct"]
    )
    assert contract.is_satisfied() is False

    contract.extracted_fields["revenue_latest"] = 199999.0
    contract.extracted_fields["ebitda_latest"] = 7777.0
    assert contract.is_satisfied() is False

    contract.extracted_fields["pat_latest"] = 4321.0
    contract.extracted_fields["revenue_yoy_pct"] = 77.86
    assert contract.is_satisfied() is True
