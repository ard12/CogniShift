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
    GoalContract,
    enforce_rca_evidence_boundaries
)
from cognishift.core.document_processing.provenance import (
    extract_and_normalize_citations,
    reconcile_citations_against_evidence
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


def test_evidence_sufficiency_rejects_other_equipment_as_support():
    query = "According to the documents, what is the maintenance procedure for P-9999?"
    distractor_context = (
        "[Pump Manual | Page 30]\nP-101A and P-101B use the redundant pump auto-transfer protocol."
    )
    is_suff, reason = validate_evidence_sufficiency(query, distractor_context)
    assert is_suff is False
    assert "P-9999" in reason


def test_evidence_sufficiency_accepts_exact_requested_equipment():
    query = "According to the documents, what is the maintenance procedure for P-101A?"
    context = "[Pump Manual | Page 12]\nP-101A maintenance requires the documented isolation sequence."
    is_suff, _ = validate_evidence_sufficiency(query, context)
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


def test_extract_and_normalize_citations_handles_all_syntax_variations():
    """Verify robust extraction across bracketed, pipe, comma, and model-returned formats."""
    # Test 1: Pipe with method
    text1 = "As documented in [P-101A_SOP.pdf | Page 4 | NATIVE], the trip point is 15 bar."
    cites1 = extract_and_normalize_citations(text1)
    assert len(cites1) == 1
    assert cites1[0]["filename"] == "P-101A_SOP.pdf"
    assert cites1[0]["page"] == 4
    assert cites1[0]["method"] == "NATIVE"
    assert cites1[0]["citation_str"] == "[P-101A_SOP.pdf | Page 4 | NATIVE]"

    # Test 2: Comma and lowercase page
    text2 = "Check [Inspection_Report.pdf, page 12] for corrosion thickness."
    cites2 = extract_and_normalize_citations(text2)
    assert len(cites2) == 1
    assert cites2[0]["filename"] == "Inspection_Report.pdf"
    assert cites2[0]["page"] == 12

    # Test 3: Model citations list
    model_cites = ["HAZOP_Manual.pdf | Page 8", "[Compressor_Manual.pdf | Page 2 | OCR]"]
    cites3 = extract_and_normalize_citations(text="", model_citations=model_cites)
    assert len(cites3) == 2
    assert cites3[0]["filename"] == "HAZOP_Manual.pdf"
    assert cites3[0]["page"] == 8
    assert cites3[1]["filename"] == "Compressor_Manual.pdf"
    assert cites3[1]["page"] == 2
    assert cites3[1]["method"] == "OCR"


def test_citation_reconciliation_eliminates_page_hallucinations():
    """Verify that hallucinated page numbers are snapped to authoritative retrieved chunks."""
    retrieved_evidence = [
        {"filename": "API610_Pumps.pdf", "page": 14, "extraction_method": "native"},
        {"filename": "HAZOP_Report.pdf", "page": 3, "extraction_method": "ocr"}
    ]
    # Model hallucinated page 99 for API610_Pumps.pdf
    model_cites = ["API610_Pumps.pdf | Page 99"]
    text = "The minimum flow rate is specified in [API610_Pumps.pdf | Page 99]."

    verified, sources_str = reconcile_citations_against_evidence(
        text=text,
        model_citations=model_cites,
        retrieved_evidence=retrieved_evidence,
        fallback_to_evidence_if_empty=False
    )
    assert len(verified) == 1
    # Page must be snapped to true retrieved page 14
    assert verified[0]["page"] == 14
    assert verified[0]["filename"] == "API610_Pumps.pdf"
    assert "[API610_Pumps.pdf | Page 14 | NATIVE]" in sources_str


def test_citation_reconciliation_filters_sources_used_to_verified_subset():
    """Verify that sources_used only includes chunks actually cited, not all retrieved chunks."""
    retrieved_evidence = [
        {"filename": "DocA.pdf", "page": 1, "extraction_method": "native"},
        {"filename": "DocA.pdf", "page": 4, "extraction_method": "native"},
        {"filename": "DocB.pdf", "page": 9, "extraction_method": "ocr"}
    ]
    # Model only referenced DocA Page 4
    model_cites = ["DocA.pdf | Page 4"]
    text = "Based on [DocA.pdf | Page 4 | NATIVE], the maximum pressure is 25 bar."

    verified, sources_str = reconcile_citations_against_evidence(
        text=text,
        model_citations=model_cites,
        retrieved_evidence=retrieved_evidence,
        fallback_to_evidence_if_empty=False
    )
    assert len(verified) == 1
    assert verified[0]["filename"] == "DocA.pdf"
    assert verified[0]["page"] == 4
    # DocA Page 1 and DocB Page 9 must NOT be in sources_str
    assert "DocB" not in sources_str
    assert "Page 1" not in sources_str
    assert sources_str == "[DocA.pdf | Page 4 | NATIVE]"


def test_enforce_rca_evidence_boundaries_preserves_verified_citations():
    """Verify that enforce_rca_evidence_boundaries preserves document citations in troubleshooting output."""
    raw_content = (
        "## Hypotheses\n"
        "- Impeller cavitation or suction strainer clogging.\n"
        "## Evidence Needed\n"
        "- Differential pressure across suction strainer.\n"
    )
    citations = ["[MRPL_Pump_Operations_Manual.pdf | Page 14 | NATIVE]"]
    rca_result = enforce_rca_evidence_boundaries(
        content=raw_content,
        operator_input="suction pressure dropped and vibration increased sharply",
        citations=citations
    )
    assert "## Documented SOP & Baseline Evidence" in rca_result
    assert "[MRPL_Pump_Operations_Manual.pdf | Page 14 | NATIVE]" in rca_result
    assert "Confirmed Observations" in rca_result

