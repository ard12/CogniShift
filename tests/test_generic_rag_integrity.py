"""
Regression test suite for generic RAG query citation integrity (Amendment 1).
Tests that ordinary KNOWLEDGE_QUERY and CSV queries adhere strictly to evidence truth:
1. SOP manual query: only actual supporting SOP evidence may appear, no unrelated P&ID/inspection citation,
   no automatic retrieval-to-citation fallback, and abstains if SOP is not in allowed sources.
2. Native CSV query: requested CSV must be retrieved and bound as evidence with native row bounds,
   never substituted with PDF/gauge images or manufactured pages.
"""
import pytest
from pathlib import Path

from cognishift.core.document_processing.provenance import (
    format_grounded_citation,
    reconcile_citations_against_evidence,
)
from cognishift.core.rca.schemas import (
    EvidenceRole,
    RCAStatus,
    RCAEvidenceItem,
    RCAEvidenceBundle,
    ChannelExecutionHealth,
    EvidenceLocator,
)
from cognishift.core.rca.evidence_validation import RCAEvidenceValidator
from cognishift.evaluation.rca_evaluator import evaluate_rca_evidence_chain_independently


def test_generic_rag_sop_query_only_cites_sop():
    """
    Test: 'What are the main steps to service pump P-101A according to the manual?'
    Ensures only actual supporting SOP evidence appears, and unrelated P&ID/inspection
    citations are not included or bound.
    """
    sop_item = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=1,
        source_id=101,
        filename="Pump_Maintenance_SOP.pdf",
        page_number=4,
        retrieval_channel="text",
        evidence_role=EvidenceRole.SOP_BASELINE,
        content="Step 1: Isolate suction and discharge valves. Step 2: Lock out motor breaker.",
        confidence=0.95,
        equipment_ids=["P-101A"],
        locator=EvidenceLocator(kind="page", document_type="pdf", filename="Pump_Maintenance_SOP.pdf", page_number=4)
    )
    distractor_pid = RCAEvidenceItem(
        evidence_id="E2",
        source_type="pdf",
        workspace_id=1,
        source_id=102,
        filename="PID-101_Pump_P101A_Suction_Loop.pdf",
        page_number=1,
        retrieval_channel="text",
        evidence_role=EvidenceRole.P_AND_ID,
        content="P&ID drawing showing 4-inch suction line to P-101A.",
        confidence=0.80,
        equipment_ids=["P-101A"],
        locator=EvidenceLocator(kind="page", document_type="pdf", filename="PID-101_Pump_P101A_Suction_Loop.pdf", page_number=1)
    )

    bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        required_roles=[EvidenceRole.SOP_BASELINE],
        optional_roles=[],
        evidence_items=[sop_item, distractor_pid],
        missing_required_roles=[],
        contradictions=[],
        source_coverage={"maintenance_sop": True},
        modality_coverage={"text": True, "visual": False, "topology": False, "telemetry": False},
        channel_health=ChannelExecutionHealth(
            requested_channels=["text"],
            executed_channels=["text"],
            failed_channels=[]
        )
    )

    # Valid response citing only SOP
    valid_output = (
        "## Confirmed Observations\n"
        "- [E1] Service procedure requires isolation and lockout: Step 1 isolate valves, Step 2 lock out breaker.\n\n"
        "## Primary Cause\n"
        "**Cause Code:** `PROCEDURE_EXECUTION`\n"
        "Routine maintenance requires adherence to SOP isolation steps [E1].\n\n"
        "## Sources\n"
        "- `Pump_Maintenance_SOP.pdf` [Pump_Maintenance_SOP.pdf | Page 4] (Channel: TEXT)"
    )

    validator = RCAEvidenceValidator()
    result = validator.validate_and_finalize(
        bundle=bundle,
        model_output=valid_output,
        operator_input="What are the main steps to service pump P-101A according to the manual?"
    )

    assert "Pump_Maintenance_SOP.pdf" in result
    assert "PID-101_Pump_P101A_Suction_Loop.pdf" not in result
    assert "[E1]" in result

    eval_res = evaluate_rca_evidence_chain_independently(
        result_text=result,
        bundle=bundle,
        structured_result=validator._last_structured_result,
        valid_filenames={"Pump_Maintenance_SOP.pdf", "PID-101_Pump_P101A_Suction_Loop.pdf"}
    )
    assert eval_res.benchmark_evidence_chain_valid is True


def test_generic_rag_sop_abstains_when_sop_missing():
    """
    If SOP is not in allowed sources or missing from vault, answer must abstain
    from claiming the manual procedure.
    """
    inspection_item = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=1,
        source_id=103,
        filename="P-101A_Inspection_Report.pdf",
        page_number=2,
        retrieval_channel="text",
        evidence_role=EvidenceRole.INSPECTION,
        content="Vibration measurements recorded 7.2 mm/s on drive-end bearing.",
        confidence=0.90,
        equipment_ids=["P-101A"],
        locator=EvidenceLocator(kind="page", document_type="pdf", filename="P-101A_Inspection_Report.pdf", page_number=2)
    )

    bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        required_roles=[EvidenceRole.SOP_BASELINE],
        optional_roles=[],
        evidence_items=[inspection_item],
        missing_required_roles=[EvidenceRole.SOP_BASELINE],
        contradictions=[],
        source_coverage={"maintenance_sop": False},
        modality_coverage={"text": True, "visual": False, "topology": False, "telemetry": False},
        channel_health=ChannelExecutionHealth(
            requested_channels=["text"],
            executed_channels=["text"],
            failed_channels=[]
        )
    )

    validator = RCAEvidenceValidator()
    result = validator.validate_and_finalize(
        bundle=bundle,
        model_output="The pump manual is missing from the repository.",
        operator_input="What are the main steps to service pump P-101A according to the manual?"
    )

    assert "INSUFFICIENT_EVIDENCE" in result
    assert validator._last_structured_result.status == RCAStatus.INSUFFICIENT_EVIDENCE.value


def test_generic_rag_csv_query_native_provenance():
    """
    Test: 'look through equipment_readings.csv — when did P-101A pressure behave strangely, and make a simple chart?'
    Ensures requested CSV is retrieved and bound with native row-range coordinates,
    never substituted with PDF/gauge images or manufactured pages.
    """
    csv_loc = EvidenceLocator(
        kind="row_range",
        document_type="csv",
        filename="equipment_readings.csv",
        row_start=15,
        row_end=35
    )

    csv_item = RCAEvidenceItem(
        evidence_id="E1",
        source_type="csv",
        workspace_id=1,
        source_id=201,
        filename="equipment_readings.csv",
        page_number=None,
        retrieval_channel="text",
        evidence_role=EvidenceRole.LIVE_TELEMETRY,
        content="timestamp,tag,pressure_bar,temp_c\n2026-09-01T04:12:00,P-101A,1.2,65.4\n2026-09-01T04:13:00,P-101A,0.4,68.2",
        confidence=0.99,
        equipment_ids=["P-101A"],
        locator=csv_loc
    )

    bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        required_roles=[EvidenceRole.LIVE_TELEMETRY],
        optional_roles=[],
        evidence_items=[csv_item],
        missing_required_roles=[],
        contradictions=[],
        source_coverage={"telemetry": True},
        modality_coverage={"text": True, "visual": False, "topology": False, "telemetry": True},
        channel_health=ChannelExecutionHealth(
            requested_channels=["text"],
            executed_channels=["text"],
            failed_channels=[]
        )
    )

    model_output = (
        "## Confirmed Observations\n"
        "- [E1] At 04:13:00, P-101A pressure dropped abruptly to 0.4 bar.\n\n"
        "## Primary Cause\n"
        "**Cause Code:** `SUCTION_STARVATION_CAVITATION`\n"
        "Sudden pressure decay observed in telemetry [E1].\n\n"
        "## Sources\n"
        "- `equipment_readings.csv` [equipment_readings.csv | Rows 15-35] (Channel: TEXT)"
    )

    validator = RCAEvidenceValidator()
    result = validator.validate_and_finalize(
        bundle=bundle,
        model_output=model_output,
        operator_input="look through equipment_readings.csv — when did P-101A pressure behave strangely, and make a simple chart?"
    )

    # Invariant: CSV must cite Rows, never Page
    assert "equipment_readings.csv" in result
    assert "[equipment_readings.csv | Rows 15-35]" in result
    assert "Page" not in result

    eval_res = evaluate_rca_evidence_chain_independently(
        result_text=result,
        bundle=bundle,
        structured_result=validator._last_structured_result,
        valid_filenames={"equipment_readings.csv"}
    )
    assert eval_res.benchmark_evidence_chain_valid is True
    assert eval_res.divergence_detected is False


def test_reconcile_citations_against_evidence_strict_no_page_snapping():
    """
    Strict citation reconciliation invariant:
    If candidate citation cites a nonexistent page (e.g. Page 99),
    it must NOT be snapped to nearest retrieved page (e.g. Page 14).
    It must be rejected as unverified.
    """
    retrieved_evidence = [
        {
            "filename": "Pump_Maintenance_SOP.pdf",
            "page": 14,
            "document_type": "pdf",
            "extraction_method": "native"
        }
    ]

    candidate_hallucinated = "According to [Pump_Maintenance_SOP.pdf | Page 99], lubrication is monthly."
    verified, sources_used = reconcile_citations_against_evidence(
        text=candidate_hallucinated,
        retrieved_evidence=retrieved_evidence,
        fallback_to_evidence_if_empty=False
    )

    # Page 99 must NOT be verified or snapped to Page 14
    assert len(verified) == 0
    assert "None (No matching manual found)" in sources_used


def test_format_grounded_citation_native_csv():
    """Tests that format_grounded_citation produces [filename.csv | Rows X-Y] without Page."""
    meta = {
        "filename": "sensor_logs.csv",
        "document_type": "csv",
        "row_start": 40,
        "row_end": 80
    }
    cite = format_grounded_citation(meta)
    assert cite == "[sensor_logs.csv | Rows 40-80]"
    assert "Page" not in cite
