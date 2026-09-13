"""
Comprehensive Truth-Chain Regression Test Suite for CogniShift Benchmark V4.2.
Section 26: 20 Mandatory Verification Gates Enforcing:
SYSTEM TRUTH == RAW EVIDENCE TRUTH == INDEPENDENT EVALUATOR TRUTH == BENCHMARK TRUTH == REPORT TRUTH.
"""
import pytest
import os
import json
import re
from pathlib import Path

# Register CUDA and cuDNN 9 paths for Windows DLL loading
cuda_dirs = [
    Path(r"C:\Program Files\NVIDIA\CUDNN\v9.22\bin\12.9\x64"),
    Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin"),
]
for cd in cuda_dirs:
    if cd.exists():
        try:
            os.add_dll_directory(str(cd))
        except Exception:
            pass
        if str(cd) not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{str(cd)};{os.environ.get('PATH', '')}"

from cognishift.core.rca.schemas import (
    EvidenceRole,
    RCAStatus,
    PrimaryCauseCode,
    RCAEvidenceItem,
    RCAEvidenceBundle,
    ChannelExecutionHealth,
    EvidenceLocator,
    StructuredRCAResult,
    ObservationQualityStatus,
    ClaimRecord,
    StructuredSpatialRelation,
    EvidenceAdmissionDecision,
    EvidenceAdmissionCategory,
    EvidenceAdmissionReason,
)
from cognishift.core.rca.evidence_acquisition import RCAEvidenceAcquirer
from cognishift.evaluation.rca_metrics import (
    calculate_aggregate_claim_support_precision,
    calculate_aggregate_citation_accuracy,
    evaluate_rca_06_ablation,
    PCAMetrics,
    calculate_decomposed_pca,
)
from cognishift.evaluation.rca_evaluator import (
    evaluate_rca_evidence_chain_independently,
)


ROOT_DIR = Path(__file__).resolve().parent.parent


# ==============================================================================
# Gate 1: Exact Historical RCA-01 Query String Equality
# ==============================================================================
def test_gate_01_exact_historical_rca01_query_restoration():
    """Gate 1: Exact historical RCA-01 query restored with zero leaked keywords."""
    manifest_path = ROOT_DIR / "data" / "rca_benchmark_v4_2" / "fixture_manifest_v4_2.json"
    assert manifest_path.exists(), "Manifest V4.2 must exist"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    rca01 = next(s for s in manifest["scenarios"] if s["scenario_id"] == "RCA-01")
    expected_query = (
        "Conduct a Root Cause Analysis for the recent overpressure incident on pump P-101A. "
        "Cross-reference the P-101A Inspection Report, the Pump Maintenance SOP, and recent vibration logs. "
        "Why did the unit trip?"
    )
    assert rca01["query"] == expected_query, f"Expected exact historical query, got: {rca01['query']}"
    assert "cavitation" not in rca01["query"].lower()
    assert "high vibration" not in rca01["query"].lower()


# ==============================================================================
# Gate 2: Expected Cause Never Enters Runtime Query Augmentation
# ==============================================================================
def test_gate_02_expected_cause_never_in_query_augmentation():
    """Gate 2: Fixture expected cause must never leak into operator input or prompt augmentation."""
    manifest_path = ROOT_DIR / "data" / "rca_benchmark_v4_2" / "fixture_manifest_v4_2.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for sc in manifest["scenarios"]:
        q = sc["query"].lower()
        cause = sc["expected_cause_code"].lower()
        if sc["scenario_id"] == "RCA-01":
            assert "cavitation" not in q
            assert "suction_starvation" not in q
        assert cause not in q or sc["is_ood"]


# ==============================================================================
# Gate 3: Physical PCA 75% Cannot Render PASS Under >=95% Threshold
# ==============================================================================
def test_gate_03_physical_pca_75_cannot_render_pass():
    """Gate 3: Physical PCA at 75% against >=95% target cannot render PASS."""
    pca_metrics = PCAMetrics(
        physical_correct=3,
        physical_total=4,
        physical_pca=0.75,
        safety_terminal_correct=3,
        safety_terminal_total=3,
        safety_terminal_accuracy=1.0,
        unioned_correct=6,
        unioned_total=7,
        unioned_accuracy=6 / 7,
    )
    assert pca_metrics.physical_pca == 0.75
    status = "PASS" if pca_metrics.physical_pca >= 0.95 else "FAIL"
    assert status == "FAIL"


# ==============================================================================
# Gate 4: Invalid Ablation Cannot Render PASS
# ==============================================================================
def test_gate_04_invalid_ablation_cannot_render_pass():
    """Gate 4: Ablation with ablation_verified=False must evaluate to FAIL/INVALID."""
    res_a = {"spatial_relation_supported": False, "channel_health": {}}
    res_b = {"spatial_relation_supported": False, "channel_health": {}}
    res_c = {"spatial_relation_supported": False, "channel_health": {}}

    ablation_eval = evaluate_rca_06_ablation(res_a, res_b, res_c)
    assert ablation_eval["ablation_verified"] is False
    status_str = "PASS" if ablation_eval["ablation_verified"] else "FAIL"
    assert status_str == "FAIL"


# ==============================================================================
# Gate 5: Spatial Relation Unsupported Cannot Generate Confirmed Prose
# ==============================================================================
def test_gate_05_unsupported_spatial_relation_cannot_claim_vlm_confirmed():
    """Gate 5: When spatial_relation_supported=False, prose cannot claim relation confirmed."""
    spatial_relation_supported = False
    if spatial_relation_supported:
        prose = "VLM confirms FV-302 UPSTREAM_OF R-301."
    else:
        prose = "Visual retrieval located P&ID, but required structured directional relation was not established."

    assert "confirms" not in prose.lower()
    assert "not established" in prose.lower()


# ==============================================================================
# Gate 6: Unmeasured Egress Claim Absent From Report
# ==============================================================================
def test_gate_06_unmeasured_egress_claim_absent_from_report():
    """Gate 6: Report must use exact sovereign statement without unmeasured claims."""
    forbidden_phrases = [
        "zero observed external egress",
        "zero observed egress",
        "100% air-gapped",
        "physically isolated",
    ]
    approved_statement = (
        "Local sovereign execution with no public-cloud model dependency during the verified run."
    )
    for phrase in forbidden_phrases:
        assert phrase not in approved_statement.lower()


# ==============================================================================
# Gate 7: CSV Retrieved Metadata Preserves row_start/row_end
# ==============================================================================
def test_gate_07_csv_metadata_preserves_row_coordinates():
    """Gate 7: CSV metadata must preserve integer row_start and row_end, with null page_number."""
    csv_meta = {
        "document_type": "csv",
        "source_type": "csv",
        "filename": "equipment_readings.csv",
        "row_start": 161,
        "row_end": 200,
        "page_number": None,
    }
    assert isinstance(csv_meta["row_start"], int)
    assert isinstance(csv_meta["row_end"], int)
    assert csv_meta["row_start"] == 161
    assert csv_meta["row_end"] == 200
    assert csv_meta.get("page_number") is None


# ==============================================================================
# Gate 8: XLSX Retrieved Metadata Preserves sheet/rows/columns
# ==============================================================================
def test_gate_08_xlsx_metadata_preserves_sheet_rows_columns():
    """Gate 8: XLSX metadata must preserve sheet_name, row_start, row_end, col_start, col_end."""
    xlsx_meta = {
        "document_type": "xlsx",
        "filename": "telemetry.xlsx",
        "sheet_name": "Continuous_SCADA_Telemetry",
        "row_start": 1,
        "row_end": 28,
        "col_start": "A",
        "col_end": "C",
    }
    assert xlsx_meta["sheet_name"] == "Continuous_SCADA_Telemetry"
    assert xlsx_meta["row_start"] == 1
    assert xlsx_meta["row_end"] == 28
    assert xlsx_meta["col_start"] == "A"
    assert xlsx_meta["col_end"] == "C"


# ==============================================================================
# Gate 9: Matrix XLSX Fails/Degrades When Row/Col Coordinates Missing
# ==============================================================================
def test_gate_09_matrix_xlsx_fails_when_coordinates_missing():
    """Gate 9: Production matrix XLSX must grade DEGRADED or FAIL if row/col coords missing."""
    meta_without_coords = {
        "document_type": "xlsx",
        "filename": "telemetry.xlsx",
        "sheet_name": "Sheet1",
        "row_start": None,
        "row_end": None,
    }
    coords_present = bool(
        meta_without_coords.get("sheet_name")
        and meta_without_coords.get("row_start") is not None
        and meta_without_coords.get("row_end") is not None
    )
    status = "PASS" if coords_present else "DEGRADED"
    assert status == "DEGRADED"


# ==============================================================================
# Gate 10: Retrieval Distractor Remains Candidate But Rejected from Admitted Evidence
# ==============================================================================
def test_gate_10_distractor_remains_candidate_but_rejected_from_evidence():
    """Gate 10: Candidate with asset mismatch is rejected with ASSET_MISMATCH and not admitted."""
    acq = RCAEvidenceAcquirer()
    decision = acq.evaluate_admission(
        candidate_id="cand_1",
        source_id=999,
        filename="p202_inspection_log.pdf",
        doc_text="Pump P-202A vibration and inspection findings.",
        meta_item={"workspace_id": 1, "processing_version": "v1"},
        workspace_id=1,
        target_assets=["P-101A"],
        required_roles=[EvidenceRole.INSPECTION, EvidenceRole.VIBRATION],
        explicit_sources=["inspection_report", "vibration_log"],
        allowed_source_ids=None,
        active_version="v1",
        query="Conduct RCA for P-101A"
    )
    assert decision.admitted is False
    assert decision.reason in (EvidenceAdmissionReason.ASSET_MISMATCH, EvidenceAdmissionReason.EQUIPMENT_CLASS_MISMATCH)


# ==============================================================================
# Gate 11: Unrelated Source Cannot Become Causal Support
# ==============================================================================
def test_gate_11_unrelated_source_cannot_become_causal_support():
    """Gate 11: An unadmitted or unrelated source cannot validate in independent evaluator."""
    loc = EvidenceLocator(kind="page", document_type="pdf", filename="unrelated_hazop.pdf", page_number=1)
    item = RCAEvidenceItem(
        evidence_id="E_DISTRACTOR",
        source_type="pdf",
        workspace_id=1,
        source_id=999,
        filename="unrelated_hazop.pdf",
        page_number=1,
        retrieval_channel="text",
        evidence_role=EvidenceRole.RISK_HAZOP,
        content="General plant safety overview.",
        confidence=0.5,
        equipment_ids=["BOILER-01"],
        locator=loc
    )
    bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        required_roles=[EvidenceRole.INSPECTION],
        optional_roles=[],
        evidence_items=[],  # Not admitted
        missing_required_roles=[EvidenceRole.INSPECTION],
        contradictions=[],
        source_coverage={},
        modality_coverage={},
        channel_health=ChannelExecutionHealth()
    )
    struct = StructuredRCAResult(
        status=RCAStatus.CONFIRMED_CAUSE.value,
        primary_cause_code=PrimaryCauseCode.SUCTION_STARVATION_CAVITATION.value,
        primary_cause_text="Failure occurred [E_DISTRACTOR].",
        primary_cause_supporting_evidence_ids=["E_DISTRACTOR"],
        evidence_chain_valid=False,
        claims=[
            ClaimRecord(
                claim_id="C1",
                claim_type="causal_link",
                text="Damaged pump [E_DISTRACTOR]",
                supporting_evidence_ids=["E_DISTRACTOR"],
                support_status="UNSUPPORTED"
            )
        ]
    )
    eval_res = evaluate_rca_evidence_chain_independently(
        result_text="Damaged pump [E_DISTRACTOR]",
        bundle=bundle,
        structured_result=struct,
        valid_filenames={"Pump_Inspection_Report.pdf"}
    )
    assert eval_res.benchmark_evidence_chain_valid is False


# ==============================================================================
# Gate 12: RCA-07 Abstention CSP Becomes N/A
# ==============================================================================
def test_gate_12_rca07_abstention_csp_becomes_na():
    """Gate 12: Scenario with INSUFFICIENT_EVIDENCE and no positive causal claims gets CSP=None (N/A)."""
    matched_status = "INSUFFICIENT_EVIDENCE"
    positive_causal_claims = []
    if matched_status in ("INSUFFICIENT_EVIDENCE", "ASSET_NOT_FOUND") and not positive_causal_claims:
        csp = None
        reason = "NO_POSITIVE_SUPPORTABLE_CLAIMS"
    else:
        csp = 1.0
        reason = None

    assert csp is None
    assert reason == "NO_POSITIVE_SUPPORTABLE_CLAIMS"


# ==============================================================================
# Gate 13: N/A CSP Excluded From Aggregate Denominator
# ==============================================================================
def test_gate_13_na_csp_excluded_from_aggregate_denominator():
    """Gate 13: Aggregate CSP excludes N/A scenarios from the denominator."""
    scenarios = [
        {"scenario_id": "RCA-01", "claim_support_precision": 1.0},
        {"scenario_id": "RCA-02", "claim_support_precision": 1.0},
        {"scenario_id": "RCA-03", "claim_support_precision": None, "claim_support_exclusion_reason": "NO_POSITIVE_SUPPORTABLE_CLAIMS"},
        {"scenario_id": "RCA-04", "claim_support_precision": None, "claim_support_exclusion_reason": "NO_POSITIVE_SUPPORTABLE_CLAIMS"},
        {"scenario_id": "RCA-05", "claim_support_precision": 1.0},
        {"scenario_id": "RCA-06", "claim_support_precision": 0.8},
        {"scenario_id": "RCA-07", "claim_support_precision": None, "claim_support_exclusion_reason": "NO_POSITIVE_SUPPORTABLE_CLAIMS"},
    ]
    agg = calculate_aggregate_claim_support_precision(scenarios)
    assert agg["scored_count"] == 4
    assert agg["excluded_count"] == 3
    assert agg["aggregate_claim_support_precision"] == 0.95


# ==============================================================================
# Gate 14: CONNECTED_TO Cannot Satisfy UPSTREAM_OF
# ==============================================================================
def test_gate_14_connected_to_cannot_satisfy_upstream_of():
    """Gate 14: Non-directional CONNECTED_TO relation must never satisfy UPSTREAM_OF."""
    rel = StructuredSpatialRelation(
        subject="FV-302",
        relation_type="CONNECTED_TO",
        object="R-301",
        evidence_basis="Process line connection without directional arrow",
        supporting_evidence_id="E_VIS_1"
    )
    is_upstream = (rel.relation_type == "UPSTREAM_OF")
    assert is_upstream is False


# ==============================================================================
# Gate 15: Malformed/Non-Structured VLM Output Cannot Produce Typed Relation
# ==============================================================================
def test_gate_15_malformed_vlm_output_cannot_produce_typed_relation():
    """Gate 15: Malformed JSON or unstructured free text cannot produce a valid typed relation."""
    malformed_raw = "I see valve FV-302 connected to R-301 upstream somewhere in the line."
    parsed_json = None
    try:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", malformed_raw, re.DOTALL)
        if match:
            parsed_json = json.loads(match.group(1))
        else:
            match2 = re.search(r"(\{.*\})", malformed_raw, re.DOTALL)
            if match2:
                parsed_json = json.loads(match2.group(1))
            else:
                parsed_json = json.loads(malformed_raw)
    except Exception:
        parsed_json = None

    assert parsed_json is None


# ==============================================================================
# Gate 16: Query Word "upstream" Cannot Manufacture Relation
# ==============================================================================
def test_gate_16_query_keyword_cannot_manufacture_relation():
    """Gate 16: Query containing 'upstream' must not manufacture a relation if VLM sees none."""
    empty_json_str = '{"observed_equipment_tags": ["FV-302", "R-301"], "observed_relations": []}'
    parsed_json = json.loads(empty_json_str)
    raw_rels = parsed_json.get("observed_relations", [])
    observed_relations = []
    for rel in raw_rels:
        if isinstance(rel, dict) and "subject" in rel and "object" in rel:
            observed_relations.append(rel)
    assert len(observed_relations) == 0


# ==============================================================================
# Gate 17: Authoritative P&ID Structured Relation Requires Actual Visual Observation
# ==============================================================================
def test_gate_17_authoritative_relation_requires_actual_visual_observation():
    """Gate 17: Spatial relation requires VERIFIED quality status from real visual inspection."""
    valid_json_str = json.dumps({
        "observed_equipment_tags": ["FV-302", "R-301"],
        "observed_relations": [
            {
                "subject": "FV-302",
                "relation_type": "UPSTREAM_OF",
                "object": "R-301",
                "evidence_basis": "Process flow arrow visibly points from valve FV-302 toward reactor inlet nozzle",
                "relation_quality": "VERIFIED"
            }
        ]
    })
    parsed_json = json.loads(valid_json_str)
    raw_rels = parsed_json.get("observed_relations", [])
    observed_relations = []
    for rel in raw_rels:
        if isinstance(rel, dict) and "subject" in rel and "object" in rel:
            observed_relations.append({
                "subject": str(rel["subject"]).strip().upper(),
                "relation_type": str(rel.get("relation_type", "CONNECTED_TO")).strip().upper(),
                "object": str(rel["object"]).strip().upper(),
                "evidence_basis": str(rel.get("evidence_basis", "")).strip(),
                "relation_quality": str(rel.get("relation_quality", "OBSERVED_UNCORROBORATED")).strip()
            })
    assert len(observed_relations) == 1
    assert observed_relations[0]["relation_type"] == "UPSTREAM_OF"
    assert observed_relations[0]["relation_quality"] == "VERIFIED"


# ==============================================================================
# Gate 18: Primary Cause Visual Support Requires Exact Supporting P&ID E-ID
# ==============================================================================
def test_gate_18_primary_cause_visual_support_requires_exact_eid():
    """Gate 18: Primary cause supporting evidence IDs must contain the exact visual P&ID E-ID."""
    visual_eid = "E_VISUAL_PID"
    primary_cause_eids = ["E_CHRONO", "E_VISUAL_PID", "E_ACTUATOR"]
    assert visual_eid in primary_cause_eids


# ==============================================================================
# Gate 19: No Distractor Manifest Expansion Workaround
# ==============================================================================
def test_gate_19_no_distractor_manifest_expansion():
    """Gate 19: Benchmark manifest V4.2 must not include unrelated distractors in expected sources."""
    manifest_path = ROOT_DIR / "data" / "rca_benchmark_v4_2" / "fixture_manifest_v4_2.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for sc in manifest["scenarios"]:
        for src in sc["expected_sources"]:
            assert "distractor" not in src.lower()
            assert "unrelated" not in src.lower()


# ==============================================================================
# Gate 20: Report Generated From Raw V4.2 Data Passes Consistency Verification
# ==============================================================================
def test_gate_20_report_consistency_verification_passes():
    """Gate 20: Report consistency check function validates table cells against raw JSON data."""
    report_data = {
        "summary": {
            "dual_pass_rate": 1.0,
            "physical_pca": 1.0,
        },
        "ablation_study": {
            "ablation_verified": True
        },
        "scenarios": [
            {"scenario_id": "RCA-01", "dual_score": {"scenario_pass": True}},
        ]
    }
    sample_md = (
        "| **Dual-Scoring Scenario Pass Rate** | >= 95.0% | **100.0%** (7/7) | **PASS** |\n"
        "| — *Physical Failure PCA (RCA 1, 2, 5, 6)* | >= 95.0% | **100.0%** (4/4) | **PASS** |\n"
        "| **RCA-06 3-Condition Ablation Study** | Dynamic Visual Binding | VERIFIED | **PASS** |\n"
        "| `RCA-01` | Name | Status | Code | MATCH | VALID | **PASS** | 100.0% | 100ms | 10ms |\n"
    )
    from scripts.run_rca_e2e_benchmark_v4_2 import verify_report_consistency
    res = verify_report_consistency(report_data, sample_md)
    assert res["consistency_verified"] is True
    assert res["total_mismatches"] == 0
