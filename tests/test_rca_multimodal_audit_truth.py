"""
Test suite for CogniShift Hybrid Multimodal RCA Verification & Benchmark Truth Audit.
Verifies:
1. 9-Point Fail-Closed Visual Runtime Preflight Assertion
2. True 3-Condition Ablation Study Evaluation (RCA-06)
3. Decomposed Citation Metrics (Source, Locator, Claim Binding)
4. Decomposed Source Coverage (Availability vs Accounting Completeness)
5. Decomposed Primary Cause Accuracy (Physical PCA vs Safety/Terminal State)
6. Strict False Cause Rate (FCR)
7. Multi-Archetype Format-Aware Locators (PDF, Scanned, P&ID, Table, XLSX, DOCX)
8. Complete Architectural Separation of Production Policy vs Benchmark Evaluation
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cognishift.app.config import settings
from cognishift.core.rca.schemas import (
    EvidenceRole,
    RCAStatus,
    PrimaryCauseCode,
    EvidenceLocator,
    RCAEvidenceItem,
    RCAEvidenceBundle,
    ChannelExecutionHealth,
)
from cognishift.evaluation.rca_metrics import (
    calculate_decomposed_citation_metrics,
    calculate_decomposed_source_coverage,
    calculate_decomposed_pca,
    calculate_false_cause_rate,
    evaluate_rca_06_ablation,
    CitationMetrics,
    SourceCoverageMetrics,
    PCAMetrics,
)
from cognishift.core.rca.evidence_acquisition import validate_full_multimodal_runtime


# 1. 9-Point Preflight Assertion Tests
@pytest.mark.asyncio
async def test_validate_full_multimodal_runtime_live():
    """Validates that the real multimodal runtime passes all 9 preflight checks."""
    ok, msg, diag = await validate_full_multimodal_runtime(workspace_id=9998, source_id=1075)
    assert ok is True, f"Preflight failed: {msg}"
    assert "All 9 visual runtime preflight checks passed" in msg
    assert diag["point_1_colpali_enabled"] is True
    assert diag["point_2_multimodal_vision_enabled"] is True
    assert diag["point_3_weights_exist"] is True
    assert diag["point_4_provider_constructed"] is True
    assert len(diag["point_5_query_embed_shape"]) == 2
    assert diag["point_6_page_png_bytes"] > 0
    assert diag["point_8_maxsim_score"] > 0.0
    assert diag["point_9_vlm_available"] is True


@pytest.mark.asyncio
async def test_validate_full_multimodal_runtime_fails_when_colpali_disabled():
    """Validates strict fail-closed behavior when colpali_enabled is False."""
    orig = settings.colpali_enabled
    try:
        settings.colpali_enabled = False
        ok, msg, diag = await validate_full_multimodal_runtime(workspace_id=9998, source_id=1075)
        assert ok is False
        assert "Point 1 Failed" in msg
    finally:
        settings.colpali_enabled = orig


@pytest.mark.asyncio
async def test_validate_full_multimodal_runtime_fails_when_weights_missing():
    """Validates fail-closed behavior when model weights are missing."""
    orig_path = settings.colpali_model_path
    try:
        settings.colpali_model_path = Path("/nonexistent/colpali/weights")
        with patch.object(Path, "exists", return_value=False):
            ok, msg, diag = await validate_full_multimodal_runtime(workspace_id=9998, source_id=1075)
            assert ok is False
            assert "Point 3 Failed" in msg or "Point 4 Failed" in msg
    finally:
        settings.colpali_model_path = orig_path


# 2. 3-Condition Ablation Study Tests
def test_evaluate_rca_06_ablation_verified_outcome():
    """Validates evaluation when all 3 conditions strictly satisfy ablation requirements."""
    res_a = {
        "channel_health": {"executed_channels": ["text"]},
        "spatial_relation_supported": False,
        "claim_support_precision": 0.5,
        "matched_rca_status": "INSUFFICIENT_EVIDENCE",
    }
    res_b = {
        "channel_health": {"executed_channels": ["text", "topology"]},
        "spatial_relation_supported": False,
        "claim_support_precision": 0.6,
        "matched_rca_status": "PLAUSIBLE_HYPOTHESIS",
    }
    res_c = {
        "channel_health": {
            "executed_channels": ["text", "visual", "topology"],
            "visual_candidate_count": 3,
            "visual_model": "Qdrant/colmodernvbert",
            "visual_device": "cuda",
        },
        "spatial_relation_supported": True,
        "visual_evidence_id_present": True,
        "visual_evidence_id": "E2",
        "primary_cause_references_visual_eid": True,
        "visual_inspector_executed": True,
        "claim_support_precision": 1.0,
        "matched_rca_status": "CONFIRMED_CAUSE",
    }

    eval_res = evaluate_rca_06_ablation(res_a, res_b, res_c)
    assert eval_res["ablation_verified"] is True
    assert eval_res["verification_verdict"] == "VERIFIED"


def test_evaluate_rca_06_ablation_fails_on_topology_leak():
    """Validates that if Condition B leaks the spatial link, ablation is invalidated."""
    res_a = {
        "channel_health": {"executed_channels": ["text"]},
        "spatial_relation_supported": False,
        "matched_rca_status": "INSUFFICIENT_EVIDENCE",
    }
    res_b = {
        "channel_health": {"executed_channels": ["text", "topology"]},
        "spatial_relation_supported": True,  # LEAK!
        "matched_rca_status": "CONFIRMED_CAUSE",
    }
    res_c = {
        "channel_health": {
            "executed_channels": ["text", "visual", "topology"],
            "visual_candidate_count": 3,
        },
        "spatial_relation_supported": True,
        "visual_evidence_id_present": True,
        "visual_evidence_id": "E2",
        "primary_cause_references_visual_eid": True,
        "visual_inspector_executed": True,
        "matched_rca_status": "CONFIRMED_CAUSE",
    }

    eval_res = evaluate_rca_06_ablation(res_a, res_b, res_c)
    assert eval_res["ablation_verified"] is False
    assert "INVALID" in eval_res["verification_verdict"]


def test_evaluate_rca_06_ablation_fails_when_visual_omitted():
    """Validates that Condition C without visual E-ID binding fails the ablation check."""
    res_a = {"channel_health": {"executed_channels": ["text"]}, "spatial_relation_supported": False}
    res_b = {"channel_health": {"executed_channels": ["text", "topology"]}, "spatial_relation_supported": False}
    res_c = {
        "channel_health": {"executed_channels": ["text", "topology"]},  # Missing visual channel
        "spatial_relation_supported": True,
        "visual_evidence_id_present": False,
        "primary_cause_references_visual_eid": False,
        "visual_inspector_executed": False,
    }

    eval_res = evaluate_rca_06_ablation(res_a, res_b, res_c)
    assert eval_res["ablation_verified"] is False


# 3. Decomposed Citation Metrics Tests
def test_calculate_decomposed_citation_metrics():
    """Validates source, locator, and claim binding decomposed citation evaluation."""
    valid_names = {"pump_maintenance_sop.pdf", "telemetry_48h.xlsx", "report.docx"}
    text = (
        "Analysis observed high vibration:\n"
        "- [Pump_Maintenance_SOP.pdf | Page 16 | PDF] specifies cavitation limit.\n"
        "- [Telemetry_48H.xlsx | Sheet: SCADA | Rows 1-50 | Cols A:H | SPREADSHEET] shows vibration peak.\n"
        "- [Report.docx | Section: Audit Summary | DOCUMENT] notes recent overhaul.\n"
        "- [Unknown_Doc.pdf | Page 1] fabricated reference.\n"
    )

    metrics = calculate_decomposed_citation_metrics(text, valid_filenames=valid_names)
    assert metrics.total_citations == 4
    assert metrics.valid_source_citations == 3  # Unknown_Doc is invalid
    assert metrics.valid_locator_citations == 4  # All 4 have locator coordinates
    assert metrics.source_accuracy == 0.75
    assert metrics.locator_accuracy == 1.0
    assert len(metrics.invalid_citations) == 1
    assert "Unknown_Doc.pdf" in metrics.invalid_citations[0]["citation"]


def test_calculate_decomposed_citation_metrics_missing_locator():
    """Validates penalty when citation omits native locator coordinates."""
    valid_names = {"pump_maintenance_sop.pdf"}
    text = "- [Pump_Maintenance_SOP.pdf] missing page number."
    metrics = calculate_decomposed_citation_metrics(text, valid_filenames=valid_names)
    assert metrics.total_citations == 1
    assert metrics.valid_source_citations == 1
    assert metrics.valid_locator_citations == 0
    assert metrics.locator_accuracy == 0.0


# 4. Decomposed Source Coverage Tests
def test_calculate_decomposed_source_coverage():
    """Validates requested availability (2/3) vs requirement accounting completeness (3/3 = 100%)."""
    required = [EvidenceRole.INSPECTION, EvidenceRole.SOP_BASELINE, EvidenceRole.VIBRATION]
    found = [EvidenceRole.INSPECTION, EvidenceRole.SOP_BASELINE]
    missing = [EvidenceRole.VIBRATION]

    cov = calculate_decomposed_source_coverage(required, found, missing)
    assert cov.total_required_roles == 3
    assert cov.requested_evidence_availability == round(2 / 3, 4)
    assert cov.requirement_accounting_completeness == 1.0
    assert cov.roles_accounting[EvidenceRole.VIBRATION.value] == "MISSING"


# 5. Decomposed Primary Cause Accuracy Tests
def test_calculate_decomposed_pca():
    """Validates separation of physical failure PCA from safety/terminal state accuracy."""
    scenarios = [
        {"scenario_id": "RCA-01", "primary_cause_accuracy": 1.0, "is_ood": False},
        {"scenario_id": "RCA-02", "primary_cause_accuracy": 1.0, "is_ood": False},
        {"scenario_id": "RCA-05", "primary_cause_accuracy": 1.0, "is_ood": False},
        {"scenario_id": "RCA-06", "primary_cause_accuracy": 1.0, "is_ood": False},
        {"scenario_id": "RCA-03", "primary_cause_accuracy": 1.0, "is_ood": False},  # Safety: honest abstention
        {"scenario_id": "RCA-04", "primary_cause_accuracy": 1.0, "is_ood": True},   # Safety: OOD fast-reject
        {"scenario_id": "RCA-07", "primary_cause_accuracy": 1.0, "is_ood": False},  # Safety: inconclusive abstention
    ]

    pca_metrics = calculate_decomposed_pca(scenarios)
    assert pca_metrics.physical_total == 4
    assert pca_metrics.physical_correct == 4
    assert pca_metrics.physical_pca == 1.0
    assert pca_metrics.safety_terminal_total == 3
    assert pca_metrics.safety_terminal_correct == 3
    assert pca_metrics.safety_terminal_accuracy == 1.0
    assert pca_metrics.unioned_accuracy == 1.0


# 6. Strict False Cause Rate Tests
def test_calculate_false_cause_rate_penalizes_wrong_cause():
    """Validates that a wrong cause in PLAUSIBLE_HYPOTHESIS is strictly penalized."""
    fcr = calculate_false_cause_rate(
        matched_status="PLAUSIBLE_HYPOTHESIS",
        extracted_cause_code="BEARING_OVERHEAT",
        expected_cause_code="SUCTION_STARVATION_CAVITATION",
        csp=1.0
    )
    assert fcr == 1.0


def test_calculate_false_cause_rate_zero_for_honest_abstention():
    """Validates that honest abstention (INSUFFICIENT_EVIDENCE) has 0.0% false cause rate."""
    fcr = calculate_false_cause_rate(
        matched_status="INSUFFICIENT_EVIDENCE",
        extracted_cause_code="INSUFFICIENT_EVIDENCE",
        expected_cause_code="INSUFFICIENT_EVIDENCE",
        csp=1.0
    )
    assert fcr == 0.0


# 7. Multi-Archetype Format-Aware Locators
def test_format_locator_across_archetypes():
    """Validates native locator formatting across all 6 document archetypes."""
    # 1. Narrative PDF
    loc_pdf = EvidenceLocator(kind="page", document_type="pdf", filename="Pump_SOP.pdf", page_number=5)
    assert loc_pdf.format_locator() == "[Pump_SOP.pdf | Page 5]"

    # 2. Scanned PDF
    loc_scan = EvidenceLocator(kind="page", document_type="pdf", filename="Scan_Log.pdf", page_number=1)
    assert loc_scan.format_locator() == "[Scan_Log.pdf | Page 1]"

    # 3. P&ID Blueprint (Visual channel)
    loc_pid = EvidenceLocator(kind="page", document_type="pdf", filename="Spatial_PID.pdf", page_number=1)
    assert loc_pid.format_locator(retrieval_channel="visual") == "[Spatial_PID.pdf | Page 1 | VISUAL]"

    # 4. Dense Table
    loc_tbl = EvidenceLocator(kind="page", document_type="pdf", filename="Hex_Grid.pdf", page_number=2)
    assert loc_tbl.format_locator() == "[Hex_Grid.pdf | Page 2]"

    # 5. Spreadsheet (XLSX)
    loc_xlsx = EvidenceLocator(
        kind="spreadsheet",
        document_type="xlsx",
        filename="Telemetry.xlsx",
        sheet_name="SCADA_48H",
        row_start="10",
        row_end="50",
        col_start="B",
        col_end="F"
    )
    assert loc_xlsx.format_locator(retrieval_channel="spreadsheet") == "[Telemetry.xlsx | Sheet: SCADA_48H | Rows 10-50 | Cols B:F | SPREADSHEET]"

    # 6. Document (DOCX)
    loc_docx = EvidenceLocator(
        kind="document_section",
        document_type="docx",
        filename="Audit.docx",
        section_heading="Bearings Inspection",
        page_number=3
    )
    assert loc_docx.format_locator(retrieval_channel="document") == "[Audit.docx | Section: Bearings Inspection | Rendered Page 3 | DOCUMENT]"


# 8. Architectural Separation Test
def test_production_policy_separation():
    """Verifies that production policy module does NOT import or contain benchmark scoring functions."""
    import cognishift.core.rca.policy as prod_policy
    
    assert not hasattr(prod_policy, "evaluate_rca_06_ablation")
    assert not hasattr(prod_policy, "calculate_decomposed_citation_metrics")
    assert not hasattr(prod_policy, "calculate_decomposed_source_coverage")
    assert not hasattr(prod_policy, "calculate_decomposed_pca")
    assert not hasattr(prod_policy, "score_status_strict")
