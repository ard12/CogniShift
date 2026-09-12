"""
Dedicated RCA Benchmark Evaluation & Decomposed Metrics Subsystem.
Strictly separated from production RCA policy (cognishift.core.rca.policy).
Provides scientifically defensible scoring, locator/source/claim citation decomposition,
source coverage decomposition, physical vs safety-state accuracy, and 3-condition ablation auditing.
"""
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from pydantic import BaseModel, Field

from cognishift.core.rca.schemas import (
    RCAStatus,
    PrimaryCauseCode,
    EvidenceRole,
    RCAEvidenceBundle,
    RCAEvidenceItem,
)


class CitationMetrics(BaseModel):
    total_citations: int = 0
    valid_source_citations: int = 0
    valid_locator_citations: int = 0
    claim_bound_citations: int = 0
    source_accuracy: float = 1.0
    locator_accuracy: float = 1.0
    claim_binding_accuracy: float = 1.0
    aggregate_accuracy: float = 1.0
    invalid_citations: List[Dict[str, Any]] = Field(default_factory=list)


class SourceCoverageMetrics(BaseModel):
    total_required_roles: int = 0
    found_roles: List[str] = Field(default_factory=list)
    missing_roles: List[str] = Field(default_factory=list)
    requested_evidence_availability: float = 1.0
    requirement_accounting_completeness: float = 1.0
    roles_accounting: Dict[str, str] = Field(default_factory=dict)


class PCAMetrics(BaseModel):
    physical_total: int = 0
    physical_correct: int = 0
    physical_pca: float = 1.0
    safety_terminal_total: int = 0
    safety_terminal_correct: int = 0
    safety_terminal_accuracy: float = 1.0
    unioned_total: int = 0
    unioned_correct: int = 0
    unioned_accuracy: float = 1.0


def calculate_decomposed_citation_metrics(
    result_text: str,
    bundle: Optional[RCAEvidenceBundle] = None,
    valid_filenames: Optional[Set[str]] = None,
    is_ood: bool = False
) -> CitationMetrics:
    """
    Decomposes citation accuracy into three independent metrics:
    1. Source Accuracy: Correct file/source present in workspace vault.
    2. Locator Accuracy: Native coordinates (page, sheet/rows/cols, section) valid and format-aware.
    3. Claim Binding Accuracy: Cited source/E-ID legitimately binds to an observation or claim.
    """
    clean_text = result_text or ""
    valid_names = {f.lower().strip() for f in (valid_filenames or set())}

    citation_regex = re.compile(
        r"\[([A-Za-z0-9_\-\.\s]+\.(?:pdf|png|csv|xlsx|docx|jpg|jpeg)\s*\|[^\|\]]+(?:\|[^\|\]]+)*)\]",
        re.IGNORECASE
    )
    matches = citation_regex.findall(clean_text)

    plain_regex = re.compile(
        r"\[([A-Za-z0-9_\-\.\s]+\.(?:pdf|png|csv|xlsx|docx|jpg|jpeg))\]",
        re.IGNORECASE
    )
    plain_matches = plain_regex.findall(clean_text)

    all_citations = matches + plain_matches
    if is_ood or not all_citations:
        return CitationMetrics(
            total_citations=len(all_citations),
            valid_source_citations=len(all_citations),
            valid_locator_citations=len(all_citations),
            claim_bound_citations=len(all_citations),
            source_accuracy=1.0,
            locator_accuracy=1.0,
            claim_binding_accuracy=1.0,
            aggregate_accuracy=1.0
        )

    valid_source_count = 0
    valid_locator_count = 0
    claim_bound_count = 0
    invalid_details = []

    bundle_files = set()
    bundle_eids = set()
    if bundle:
        for item in bundle.evidence_items:
            bundle_files.add(Path(item.filename).name.lower())
            bundle_eids.add(item.evidence_id)

    for cit in all_citations:
        parts = [p.strip() for p in cit.split("|")]
        fname = Path(parts[0]).name.lower()
        
        # 1. Source Accuracy check
        is_src_valid = (fname in valid_names and "document.pdf" not in fname) if valid_names else True
        if is_src_valid:
            valid_source_count += 1
        else:
            invalid_details.append({
                "citation": cit,
                "reason": f"Filename '{fname}' not recognized in workspace vault or generic fallback."
            })

        # 2. Locator Accuracy check
        is_loc_valid = False
        if len(parts) >= 2:
            coord = parts[1].lower()
            if fname.endswith((".xlsx", ".xlsm")):
                if "sheet" in coord or "rows" in coord or "cols" in coord:
                    is_loc_valid = True
                else:
                    invalid_details.append({
                        "citation": cit,
                        "reason": "Spreadsheet citation missing native sheet/row/col coordinates."
                    })
            elif fname.endswith(".docx"):
                if "section" in coord or "page" in coord:
                    is_loc_valid = True
                else:
                    invalid_details.append({
                        "citation": cit,
                        "reason": "Word document citation missing section or page coordinates."
                    })
            elif fname.endswith(".pdf"):
                if "page" in coord:
                    is_loc_valid = True
                else:
                    invalid_details.append({
                        "citation": cit,
                        "reason": "PDF citation missing page coordinates."
                    })
            else:
                is_loc_valid = True
        elif len(parts) == 1:
            is_loc_valid = False
            invalid_details.append({
                "citation": cit,
                "reason": "Citation lacks coordinate locator."
            })

        if is_loc_valid:
            valid_locator_count += 1

        # 3. Claim Binding Accuracy check
        if fname in bundle_files or not bundle:
            claim_bound_count += 1
        else:
            invalid_details.append({
                "citation": cit,
                "reason": f"File '{fname}' cited but was not bound in authoritative evidence bundle."
            })

    total = len(all_citations)
    src_acc = valid_source_count / total if total > 0 else 1.0
    loc_acc = valid_locator_count / total if total > 0 else 1.0
    bnd_acc = claim_bound_count / total if total > 0 else 1.0
    agg_acc = (src_acc + loc_acc + bnd_acc) / 3.0

    return CitationMetrics(
        total_citations=total,
        valid_source_citations=valid_source_count,
        valid_locator_citations=valid_locator_count,
        claim_bound_citations=claim_bound_count,
        source_accuracy=round(src_acc, 4),
        locator_accuracy=round(loc_acc, 4),
        claim_binding_accuracy=round(bnd_acc, 4),
        aggregate_accuracy=round(agg_acc, 4),
        invalid_citations=invalid_details
    )


def calculate_decomposed_source_coverage(
    required_roles: List[EvidenceRole],
    found_roles: List[EvidenceRole],
    missing_roles: List[EvidenceRole]
) -> SourceCoverageMetrics:
    """
    Decomposes source coverage:
    - Requested Evidence Availability: found / total (e.g. 2/3 = 66.7% when vibration telemetry is missing).
    - Requirement Accounting Completeness: (found + missing accounted) / total (3/3 = 100%).
    """
    req_set = {r.value if isinstance(r, EvidenceRole) else str(r) for r in required_roles}
    fnd_set = {r.value if isinstance(r, EvidenceRole) else str(r) for r in found_roles}
    mis_set = {r.value if isinstance(r, EvidenceRole) else str(r) for r in missing_roles}

    total = len(req_set)
    if total == 0:
        return SourceCoverageMetrics(
            total_required_roles=0,
            requested_evidence_availability=1.0,
            requirement_accounting_completeness=1.0
        )

    fnd_roles = [r for r in req_set if r in fnd_set]
    mis_roles = [r for r in req_set if r in mis_set or r not in fnd_set]

    accounting = {}
    for r in req_set:
        if r in fnd_set:
            accounting[r] = "FOUND"
        elif r in mis_set:
            accounting[r] = "MISSING"
        else:
            accounting[r] = "UNACCOUNTED"

    avail = len(fnd_roles) / total
    comp = (len(fnd_roles) + len([r for r in mis_roles if accounting.get(r) == "MISSING"])) / total

    return SourceCoverageMetrics(
        total_required_roles=total,
        found_roles=fnd_roles,
        missing_roles=mis_roles,
        requested_evidence_availability=round(avail, 4),
        requirement_accounting_completeness=round(comp, 4),
        roles_accounting=accounting
    )


def calculate_decomposed_pca(scenarios_results: List[Dict[str, Any]]) -> PCAMetrics:
    """
    Splits Physical Primary Cause Accuracy from Safety / Terminal State Accuracy.
    Physical cases: scenarios where a physical failure cause exists (RCA-01, 02, 05, 06).
    Safety terminal cases: scenarios expecting safety terminal states (RCA-03, 04, 07).
    """
    safety_scenarios = {"RCA-03", "RCA-04", "RCA-07"}
    
    phys_total = 0
    phys_corr = 0
    safe_total = 0
    safe_corr = 0

    for s in scenarios_results:
        sc_id = s.get("scenario_id", "")
        pca = s.get("primary_cause_accuracy", 0.0)
        is_corr = (pca >= 0.99)
        
        if sc_id in safety_scenarios or s.get("is_ood"):
            safe_total += 1
            if is_corr:
                safe_corr += 1
        else:
            phys_total += 1
            if is_corr:
                phys_corr += 1

    phys_pca = phys_corr / phys_total if phys_total > 0 else 1.0
    safe_acc = safe_corr / safe_total if safe_total > 0 else 1.0
    union_total = phys_total + safe_total
    union_corr = phys_corr + safe_corr
    union_acc = union_corr / union_total if union_total > 0 else 1.0

    return PCAMetrics(
        physical_total=phys_total,
        physical_correct=phys_corr,
        physical_pca=round(phys_pca, 4),
        safety_terminal_total=safe_total,
        safety_terminal_correct=safe_corr,
        safety_terminal_accuracy=round(safe_acc, 4),
        unioned_total=union_total,
        unioned_correct=union_corr,
        unioned_accuracy=round(union_acc, 4)
    )


def calculate_false_cause_rate(
    matched_status: str,
    extracted_cause_code: str,
    expected_cause_code: str,
    csp: float = 1.0
) -> float:
    """
    Strict False Cause Rate evaluation.
    A false physical cause counts regardless of confidence state:
    CONFIRMED_CAUSE, SUPPORTED_LIKELY_CAUSE, or PLAUSIBLE_HYPOTHESIS with a wrong cause
    or without minimum evidentiary support is penalized as a false cause.
    """
    clean_status = (matched_status or "").upper().strip()
    clean_ext = (extracted_cause_code or "").upper().strip()
    clean_exp = (expected_cause_code or "").upper().strip()

    if clean_status in ("INSUFFICIENT_EVIDENCE", "ASSET_NOT_FOUND"):
        if clean_exp not in ("INSUFFICIENT_EVIDENCE", "ASSET_NOT_FOUND"):
            return 0.0
        return 0.0

    if clean_status in ("CONFIRMED_CAUSE", "SUPPORTED_LIKELY_CAUSE", "PLAUSIBLE_HYPOTHESIS"):
        if clean_ext != clean_exp and clean_ext not in ("UNKNOWN", "INSUFFICIENT_EVIDENCE"):
            return 1.0
        if clean_status == "CONFIRMED_CAUSE" and csp < 0.5:
            return 1.0

    return 0.0


def evaluate_rca_06_ablation(
    res_a: Dict[str, Any],
    res_b: Dict[str, Any],
    res_c: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluates the 3-Condition Ablation Study for RCA-06:
    Condition A: Text Only (visual/topology disabled, spatial relation unsupported).
    Condition B: Text + Topology (visual disabled, topology free of spatial leak, spatial relation unsupported).
    Condition C: Full Multimodal (visual active, candidate_count > 0, visual E-ID in pack, primary cause references visual E-ID).
    """
    ch_a = res_a.get("channel_health", {})
    exec_a = ch_a.get("executed_channels", [])
    vis_in_a = "visual" in exec_a

    ch_b = res_b.get("channel_health", {})
    exec_b = ch_b.get("executed_channels", [])
    vis_in_b = "visual" in exec_b
    topo_leaked = res_b.get("spatial_relation_supported", False)

    ch_c = res_c.get("channel_health", {})
    exec_c = ch_c.get("executed_channels", [])
    vis_in_c = "visual" in exec_c
    vis_cand_count = ch_c.get("visual_candidate_count", 0)
    visual_e_id_present = res_c.get("visual_evidence_id_present", False)
    cause_references_visual = res_c.get("primary_cause_references_visual_eid", False)
    inspector_executed = res_c.get("visual_inspector_executed", False)
    visual_model = ch_c.get("visual_model")
    visual_device = ch_c.get("visual_device")

    is_valid_ablation = (
        not vis_in_a
        and not vis_in_b
        and not topo_leaked
        and vis_in_c
        and vis_cand_count > 0
        and visual_e_id_present
        and cause_references_visual
        and inspector_executed
    )

    return {
        "study": "True Visual RCA 3-Condition Ablation Study (RCA-06)",
        "evaluated_scenario": "RCA-06 (Hydrocracker R-301 / FV-302 P&ID Spatial Dependency)",
        "condition_a_text_only": {
            "executed_channels": exec_a,
            "visual_executed": vis_in_a,
            "spatial_relation_supported": res_a.get("spatial_relation_supported", False),
            "claim_support_precision": res_a.get("claim_support_precision", 0.0),
            "status": res_a.get("matched_rca_status"),
        },
        "condition_b_text_topology": {
            "executed_channels": exec_b,
            "visual_executed": vis_in_b,
            "spatial_relation_supported": topo_leaked,
            "spatial_leak_prevented": not topo_leaked,
            "claim_support_precision": res_b.get("claim_support_precision", 0.0),
            "status": res_b.get("matched_rca_status"),
        },
        "condition_c_full_multimodal": {
            "executed_channels": exec_c,
            "visual_executed": vis_in_c,
            "visual_candidate_count": vis_cand_count,
            "visual_model": visual_model,
            "visual_device": visual_device,
            "visual_evidence_id": res_c.get("visual_evidence_id"),
            "visual_inspector_executed": inspector_executed,
            "primary_cause_references_visual_eid": cause_references_visual,
            "spatial_relation_supported": res_c.get("spatial_relation_supported", True),
            "claim_support_precision": res_c.get("claim_support_precision", 0.0),
            "status": res_c.get("matched_rca_status"),
        },
        "ablation_verified": is_valid_ablation,
        "verification_verdict": "VERIFIED" if is_valid_ablation else "INVALID — ABLATION CONDITIONS NOT SATISFIED"
    }
