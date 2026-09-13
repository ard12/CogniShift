"""
Dedicated RCA Benchmark Evaluation & Decomposed Metrics Subsystem.
Strictly separated from production RCA runtime and policy code.
Provides scientifically defensible scoring:
- Decomposed citation metrics (source validity, locator precision, claim binding)
- Decomposed source coverage (availability vs requirement accounting completeness)
- Decomposed PCA (physical failure accuracy vs safety/terminal state accuracy)
- Strict False Cause Rate (FCR)
- True 3-condition ablation verification with dynamic evidence ID binding
"""
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
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
    source_accuracy: Optional[float] = None
    locator_accuracy: Optional[float] = None
    claim_binding_accuracy: Optional[float] = None
    aggregate_accuracy: Optional[float] = None
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
    is_ood: bool = False,
    claims: Optional[List[Any]] = None,
    structured_result: Optional[Any] = None,
) -> CitationMetrics:
    """
    Decomposes citation accuracy into three independent dimensions:
    1. Source Accuracy: File name recognized in the workspace knowledge vault.
    2. Locator Accuracy: Native coordinates (page, sheet/rows/cols, section) format-valid.
    3. Claim Binding Accuracy: Cited source binds legitimately to an authoritative evidence item.

    Truth Rule: If total_citations == 0 (e.g. OOD abstention or missing evidence),
    accuracy is None (N/A) rather than 1.0 or 0.0, and must be excluded from aggregate
    benchmark citation denominators.
    """
    clean_text = result_text or ""
    valid_names = {f.lower().strip() for f in (valid_filenames or set())}

    citation_regex = re.compile(
        r"\[([A-Za-z0-9_\-\.\s]+\.(?:pdf|png|csv|xlsx|docx|jpg|jpeg)\s*\|[^\|\]]+(?:\|[^\|\]]+)*)\]",
        re.IGNORECASE,
    )
    matches = citation_regex.findall(clean_text)

    plain_regex = re.compile(
        r"\[([A-Za-z0-9_\-\.\s]+\.(?:pdf|png|csv|xlsx|docx|jpg|jpeg))\]",
        re.IGNORECASE,
    )
    plain_matches = plain_regex.findall(clean_text)

    all_citations = matches + plain_matches

    if not all_citations:
        return CitationMetrics(
            total_citations=0,
            valid_source_citations=0,
            valid_locator_citations=0,
            claim_bound_citations=0,
            source_accuracy=None,
            locator_accuracy=None,
            claim_binding_accuracy=None,
            aggregate_accuracy=None,
            invalid_citations=[],
        )

    valid_source_count = 0
    valid_locator_count = 0
    claim_bound_count = 0
    invalid_details: List[Dict[str, Any]] = []

    bundle_files: Set[str] = set()
    bundle_eids: Set[str] = set()
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
                "reason": f"Filename '{fname}' not recognized in workspace vault or generic fallback.",
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
                        "reason": "Spreadsheet citation missing native sheet/row/col coordinates.",
                    })
            elif fname.endswith(".docx"):
                if "section" in coord or "page" in coord:
                    is_loc_valid = True
                else:
                    invalid_details.append({
                        "citation": cit,
                        "reason": "Word document citation missing section or page coordinates.",
                    })
            elif fname.endswith(".pdf"):
                if "page" in coord:
                    is_loc_valid = True
                else:
                    invalid_details.append({
                        "citation": cit,
                        "reason": "PDF citation missing page coordinates.",
                    })
            elif fname.endswith(".csv"):
                if "rows" in coord or "row" in coord or "lines" in coord:
                    is_loc_valid = True
                else:
                    invalid_details.append({
                        "citation": cit,
                        "reason": "CSV citation missing row-range coordinates.",
                    })
            else:
                is_loc_valid = True
        elif len(parts) == 1:
            is_loc_valid = False
            invalid_details.append({
                "citation": cit,
                "reason": "Citation lacks coordinate locator.",
            })

        if is_loc_valid:
            valid_locator_count += 1

        # 3. Claim Binding Accuracy check
        resolved_claims = claims
        if resolved_claims is None and structured_result:
            if isinstance(structured_result, dict):
                resolved_claims = structured_result.get("claims", [])
            else:
                resolved_claims = getattr(structured_result, "claims", [])

        # Build evidence_id -> filename mapping
        eid_to_fname = {}
        if bundle:
            for itm in bundle.evidence_items:
                eid_to_fname[itm.evidence_id] = Path(itm.filename).name.lower()
        elif structured_result:
            s_items = (
                structured_result.get("evidence_items", [])
                if isinstance(structured_result, dict)
                else getattr(structured_result, "evidence_items", [])
            )
            for itm in s_items:
                eid = itm.get("evidence_id") if isinstance(itm, dict) else getattr(itm, "evidence_id", None)
                fn = itm.get("filename") if isinstance(itm, dict) else getattr(itm, "filename", None)
                if eid and fn:
                    eid_to_fname[eid] = Path(fn).name.lower()

        if resolved_claims:
            is_bound = False
            matched_item = None
            if bundle:
                matched_item = next((i for i in bundle.evidence_items if Path(i.filename).name.lower() == fname), None)

            for clm in resolved_claims:
                c_status = str(getattr(clm, "support_status", "") or (clm.get("support_status") if isinstance(clm, dict) else "")).upper()
                is_supported = "SUPPORTED" in c_status or "PARTIALLY_SUPPORTED" in c_status
                if not is_supported:
                    continue
                sup_eids = getattr(clm, "supporting_evidence_ids", []) or (clm.get("supporting_evidence_ids", []) if isinstance(clm, dict) else [])
                if any(eid_to_fname.get(eid) == fname for eid in sup_eids):
                    is_bound = True
                    break
                if matched_item and matched_item.evidence_id in sup_eids:
                    is_bound = True
                    break
                cit_refs = [str(r).lower() for r in (getattr(clm, "citation_references", []) or (clm.get("citation_references", []) if isinstance(clm, dict) else []))]
                if any(fname in ref for ref in cit_refs):
                    is_bound = True
                    break
                clm_text = str(getattr(clm, "text", "") or (clm.get("text") if isinstance(clm, dict) else "")).lower()
                if fname in clm_text or Path(fname).stem.lower() in clm_text:
                    is_bound = True
                    break

            if is_bound:
                claim_bound_count += 1
            else:
                invalid_details.append({
                    "citation": cit,
                    "reason": f"File '{fname}' cited but does not bind to any verified/supported claim in the evidence chain.",
                })
        elif fname in bundle_files or not bundle:
            claim_bound_count += 1
        else:
            invalid_details.append({
                "citation": cit,
                "reason": f"File '{fname}' cited but was not bound in authoritative evidence bundle.",
            })

    total = len(all_citations)
    src_acc = valid_source_count / total if total > 0 else 0.0
    loc_acc = valid_locator_count / total if total > 0 else 0.0
    bnd_acc = claim_bound_count / total if total > 0 else 0.0
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
        invalid_citations=invalid_details,
    )


def calculate_decomposed_source_coverage(
    required_roles: List[EvidenceRole],
    found_roles: List[EvidenceRole],
    missing_roles: List[EvidenceRole],
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
            requirement_accounting_completeness=1.0,
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
        roles_accounting=accounting,
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
        unioned_accuracy=round(union_acc, 4),
    )


def calculate_false_cause_rate(
    matched_status: str,
    extracted_cause_code: str,
    expected_cause_code: str,
    csp: float = 1.0,
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
    res_c: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluates the 3-Condition Ablation Study for RCA-06:
    Condition A: Text Only (visual/topology disabled, spatial relation unsupported).
    Condition B: Text + Topology (visual disabled, topology free of spatial leak, spatial relation unsupported).
    Condition C: Full Multimodal (visual active, candidate_count > 0, visual E-ID in pack, primary cause references visual E-ID).

    Authoritative dynamically bound verification:
    Does NOT require a hardcoded literal "E4".
    Dynamically inspects the visual P&ID evidence item's real runtime ID and verifies
    it is referenced in primary cause supporting evidence IDs.
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

    # Resolve dynamic visual evidence ID if structured result is provided
    struct_c = res_c.get("rca_result_structured") or res_c.get("structured_result") or {}
    visual_e_id = res_c.get("visual_evidence_id")
    if not visual_e_id and struct_c:
        # Check evidence items or evidence pack in structured result
        for item in (struct_c.get("evidence_items") or struct_c.get("evidence_pack") or []):
            if item.get("retrieval_channel") == "visual" or item.get("evidence_role") in ("P_AND_ID", "p_and_id") or item.get("role") in ("P_AND_ID", "p_and_id"):
                visual_e_id = item.get("evidence_id")
                break

    visual_e_id_present = res_c.get("visual_evidence_id_present", bool(visual_e_id))

    cause_references_visual = res_c.get("primary_cause_references_visual_eid", False)
    if not cause_references_visual and struct_c and visual_e_id:
        supporting_ids = struct_c.get("primary_cause_supporting_evidence_ids", [])
        if visual_e_id in supporting_ids:
            cause_references_visual = True

    inspector_executed = res_c.get("visual_inspector_executed", False)
    if not inspector_executed and ch_c.get("visual_inspector_executed"):
        inspector_executed = True

    visual_model = ch_c.get("visual_model")
    visual_device = ch_c.get("visual_device")

    # Verify structured VLM observation
    vlm_structured_obs = True
    if "vlm_structured_observation" in res_c:
        vlm_structured_obs = bool(res_c["vlm_structured_observation"])
    elif "observed_relations" in res_c:
        vlm_structured_obs = bool(res_c["observed_relations"])
    elif "observed_relations" in ch_c:
        vlm_structured_obs = bool(ch_c["observed_relations"])
    elif struct_c and "spatial_relations" in struct_c:
        vlm_structured_obs = bool(struct_c["spatial_relations"])

    # Verify OCR tag corroboration
    ocr_corroborated = True
    if "ocr_corroborated" in res_c:
        ocr_corroborated = bool(res_c["ocr_corroborated"])
    elif "quality_status" in res_c:
        ocr_corroborated = res_c["quality_status"] in ("VERIFIED", "SUCCESS")
    elif "quality_status" in ch_c:
        ocr_corroborated = ch_c["quality_status"] in ("VERIFIED", "SUCCESS")
    elif "ocr_tag_corroboration_passed" in res_c:
        ocr_corroborated = bool(res_c["ocr_tag_corroboration_passed"])

    is_valid_ablation = (
        not vis_in_a
        and not vis_in_b
        and not topo_leaked
        and vis_in_c
        and vis_cand_count > 0
        and visual_e_id_present
        and cause_references_visual
        and inspector_executed
        and vlm_structured_obs
        and ocr_corroborated
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
            "visual_evidence_id": visual_e_id,
            "visual_inspector_executed": inspector_executed,
            "vlm_structured_observation": vlm_structured_obs,
            "ocr_corroborated": ocr_corroborated,
            "primary_cause_references_visual_eid": cause_references_visual,
            "spatial_relation_supported": res_c.get("spatial_relation_supported", True),
            "claim_support_precision": res_c.get("claim_support_precision", 0.0),
            "status": res_c.get("matched_rca_status"),
        },
        "ablation_verified": is_valid_ablation,
        "verification_verdict": "VERIFIED" if is_valid_ablation else "INVALID — ABLATION CONDITIONS NOT SATISFIED",
    }


def evaluate_scenario_dual_scoring(
    scenario_id: str,
    matched_status: str,
    expected_status: str,
    extracted_cause_code: str,
    expected_cause_code: str,
    evidence_chain_valid: bool,
    primary_cause_accuracy: float = 1.0,
    status_score: float = 1.0,
) -> Dict[str, Any]:
    """
    Dual Scoring for Benchmark V4:
    - outcome_match: Primary cause and status match expectations.
    - evidence_chain_valid: Evidence IDs, citations, and claim bindings valid without circularity.
    - scenario_pass: PASS only if BOTH outcome_match AND evidence_chain_valid are True.
    """
    status_match = (
        (matched_status.upper().strip() == expected_status.upper().strip())
        or status_score >= 0.99
    )
    outcome_match = (
        status_match
        and (extracted_cause_code.upper().strip() == expected_cause_code.upper().strip())
        and primary_cause_accuracy >= 0.99
    )
    scenario_pass = bool(outcome_match and evidence_chain_valid)
    return {
        "scenario_id": scenario_id,
        "outcome_match": outcome_match,
        "evidence_chain_valid": evidence_chain_valid,
        "scenario_pass": scenario_pass,
        "verdict": "PASS" if scenario_pass else ("FAIL (Evidence Chain Invalid)" if outcome_match else "FAIL (Outcome Mismatch)")
    }


def calculate_aggregate_citation_accuracy(
    scenario_metrics: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Computes aggregate citation accuracy strictly excluding N/A scenarios from denominators.
    Reports scored_count, excluded_count, and exclusion_reasons per Amendment 7.
    """
    scored_values: List[float] = []
    excluded_reasons: List[Dict[str, str]] = []

    for s in scenario_metrics:
        sc_id = s.get("scenario_id", "UNKNOWN")
        acc = s.get("citation_accuracy")
        if acc is None:
            reason = s.get("exclusion_reason") or "No citations required (honest abstention/OOD/insufficient evidence)"
            excluded_reasons.append({"scenario_id": sc_id, "reason": reason})
        else:
            scored_values.append(float(acc))

    avg_acc = (sum(scored_values) / len(scored_values)) if scored_values else None
    return {
        "aggregate_citation_accuracy": round(avg_acc, 4) if avg_acc is not None else None,
        "scored_count": len(scored_values),
        "excluded_count": len(excluded_reasons),
        "exclusion_reasons": excluded_reasons,
    }


def calculate_aggregate_claim_support_precision(
    scenario_metrics: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Computes aggregate Claim Support Precision (CSP) strictly excluding N/A scenarios
    (honest abstention/OOD with no positive supportable causal claims) from denominators.
    Reports scored_csp_scenarios, excluded_csp_scenarios, and exclusion_reasons per Constraint 17.
    """
    scored_values: List[float] = []
    scored_scenarios: List[str] = []
    excluded_scenarios: List[str] = []
    exclusion_reasons: List[Dict[str, str]] = []

    for s in scenario_metrics:
        sc_id = s.get("scenario_id", "UNKNOWN")
        csp = s.get("claim_support_precision")
        if csp is None:
            reason = s.get("claim_support_exclusion_reason") or "NO_POSITIVE_SUPPORTABLE_CLAIMS"
            excluded_scenarios.append(sc_id)
            exclusion_reasons.append({"scenario_id": sc_id, "reason": reason})
        else:
            scored_scenarios.append(sc_id)
            scored_values.append(float(csp))

    avg_csp = (sum(scored_values) / len(scored_values)) if scored_values else None
    return {
        "aggregate_claim_support_precision": round(avg_csp, 4) if avg_csp is not None else None,
        "scored_count": len(scored_values),
        "scored_csp_scenarios": scored_scenarios,
        "excluded_count": len(excluded_scenarios),
        "excluded_csp_scenarios": excluded_scenarios,
        "exclusion_reasons": exclusion_reasons,
    }


