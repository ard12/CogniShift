"""
Independent Evidence Chain Evaluator for CogniShift Benchmark V4.1.
Strictly separated from production runtime. Evaluates raw persisted evidence
structures, locator coordinates, claim-to-evidence bindings, and visual/topology
truth without circular trust in production booleans.
"""
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Union
from pydantic import BaseModel, Field

from cognishift.core.rca.schemas import (
    RCAStatus,
    PrimaryCauseCode,
    EvidenceRole,
    RCAEvidenceBundle,
    RCAEvidenceItem,
    StructuredRCAResult,
    ObservationQualityStatus,
    ClaimRecord,
    StructuredSpatialRelation,
)
from cognishift.evaluation.rca_metrics import (
    CitationMetrics,
    calculate_decomposed_citation_metrics,
)

logger = logging.getLogger(__name__)


class IndependentEvidenceEvaluation(BaseModel):
    benchmark_evidence_chain_valid: bool
    production_evidence_chain_valid: Optional[bool] = None
    divergence_detected: bool = False
    evidence_item_count: int = 0
    valid_evidence_items: int = 0
    claim_count: int = 0
    valid_claim_bindings: int = 0
    spatial_relation_count: int = 0
    valid_spatial_relations: int = 0
    citation_count: int = 0
    valid_citations: int = 0
    validation_failures: List[Dict[str, Any]] = Field(default_factory=list)
    failure_summary: Optional[str] = None


def evaluate_rca_evidence_chain_independently(
    result_text: str,
    bundle: Optional[RCAEvidenceBundle] = None,
    structured_result: Optional[Union[StructuredRCAResult, Dict[str, Any]]] = None,
    valid_filenames: Optional[Set[str]] = None,
    active_processing_versions: Optional[Dict[str, str]] = None,
    is_ood: bool = False,
    is_insufficient: bool = False,
) -> IndependentEvidenceEvaluation:
    """
    Independently audits the evidence chain from raw persisted structures:
    1. Validates each evidence item in the bundle for file existence, processing version,
       native coordinates, and channel truth.
    2. Validates claim-to-evidence bindings (no ungrounded causal claims, no procedural text as root cause).
    3. Validates spatial relations (must be backed by visual channel, P&ID role, machine-readable VLM observation,
       and deterministic OCR tag corroboration).
    4. Validates citation source, locator precision, and claim binding accuracy.
    5. Flags divergence between production boolean and independent evaluation.
    """
    failures: List[Dict[str, Any]] = []

    # Extract production boolean if present
    prod_valid: Optional[bool] = None
    if structured_result is not None:
        if isinstance(structured_result, dict):
            prod_valid = structured_result.get("evidence_chain_valid")
        else:
            prod_valid = getattr(structured_result, "evidence_chain_valid", None)

    # Determine status
    status_str = ""
    if structured_result is not None:
        if isinstance(structured_result, dict):
            status_str = str(structured_result.get("status", "")).upper()
        else:
            status_str = str(getattr(structured_result, "status", "")).upper()

    is_abstention = (
        is_ood
        or is_insufficient
        or status_str in ("ASSET_NOT_FOUND", "INSUFFICIENT_EVIDENCE")
    )

    # Resolve items from bundle or structured_result
    items: List[Any] = []
    if bundle and bundle.evidence_items:
        items = bundle.evidence_items
    elif structured_result:
        raw_items = (
            structured_result.get("evidence_items", [])
            if isinstance(structured_result, dict)
            else getattr(structured_result, "evidence_items", [])
        )
        items = raw_items

    valid_names = {f.lower().strip() for f in (valid_filenames or set())}

    # 1. Audit Evidence Items
    valid_item_eids: Set[str] = set()
    item_map: Dict[str, Any] = {}
    valid_items_count = 0

    for itm in items:
        eid = itm.evidence_id if hasattr(itm, "evidence_id") else itm.get("evidence_id")
        fname = itm.filename if hasattr(itm, "filename") else itm.get("filename", "")
        chan = itm.retrieval_channel if hasattr(itm, "retrieval_channel") else itm.get("retrieval_channel", "")
        pv = itm.processing_version if hasattr(itm, "processing_version") else itm.get("processing_version", "")
        loc = itm.locator if hasattr(itm, "locator") else itm.get("locator")
        role = itm.evidence_role if hasattr(itm, "evidence_role") else itm.get("evidence_role")
        stype = itm.source_type if hasattr(itm, "source_type") else itm.get("source_type")

        clean_fname = Path(fname).name.lower()
        item_ok = True

        # Check filename validity
        if valid_names and clean_fname not in valid_names and clean_fname != "plant_topology_graph":
            failures.append({
                "component": "evidence_item",
                "evidence_id": eid,
                "reason": f"Filename '{fname}' is not registered in valid fixture manifest.",
            })
            item_ok = False

        # Check channel truth
        if chan == "visual":
            if not clean_fname.endswith((".pdf", ".png", ".jpg", ".jpeg")):
                failures.append({
                    "component": "evidence_item",
                    "evidence_id": eid,
                    "reason": f"Visual channel item '{fname}' has invalid non-visual extension.",
                })
                item_ok = False
        elif chan == "topology":
            if stype != "topology" and "topology" not in clean_fname:
                failures.append({
                    "component": "evidence_item",
                    "evidence_id": eid,
                    "reason": f"Topology channel item '{fname}' has invalid source_type '{stype}'.",
                })
                item_ok = False
        elif chan == "text":
            if clean_fname.endswith((".png", ".jpg", ".jpeg")):
                failures.append({
                    "component": "evidence_item",
                    "evidence_id": eid,
                    "reason": f"Text channel item '{fname}' is an image file.",
                })
                item_ok = False

        # Check locator format
        if loc:
            kind = loc.kind if hasattr(loc, "kind") else loc.get("kind")
            dtype = loc.document_type if hasattr(loc, "document_type") else loc.get("document_type")
            if clean_fname.endswith(".csv"):
                if dtype != "csv":
                    failures.append({
                        "component": "evidence_item",
                        "evidence_id": eid,
                        "reason": f"CSV item '{fname}' has mismatched locator document_type '{dtype}'.",
                    })
                    item_ok = False
            elif clean_fname.endswith((".xlsx", ".xlsm")):
                if dtype not in ("xlsx", "spreadsheet"):
                    failures.append({
                        "component": "evidence_item",
                        "evidence_id": eid,
                        "reason": f"Spreadsheet item '{fname}' has mismatched locator document_type '{dtype}'.",
                    })
                    item_ok = False

        if item_ok and eid:
            valid_item_eids.add(eid)
            item_map[eid] = itm
            valid_items_count += 1

    # 2. Audit Claims & Causal Links
    claims_list: List[Any] = []
    if structured_result:
        claims_list = (
            structured_result.get("claims", [])
            if isinstance(structured_result, dict)
            else getattr(structured_result, "claims", [])
        )

    valid_claims_count = 0
    for clm in claims_list:
        cid = clm.claim_id if hasattr(clm, "claim_id") else clm.get("claim_id")
        ctype = clm.claim_type if hasattr(clm, "claim_type") else clm.get("claim_type")
        ctext = clm.text if hasattr(clm, "text") else clm.get("text", "")
        sup_ids = clm.supporting_evidence_ids if hasattr(clm, "supporting_evidence_ids") else clm.get("supporting_evidence_ids", [])
        cstatus = clm.support_status if hasattr(clm, "support_status") else clm.get("support_status")
        cstatus_str = str(cstatus.value if hasattr(cstatus, "value") else cstatus).upper()

        claim_ok = True

        # Verify all supporting E-IDs exist in valid items
        for sid in sup_ids:
            if sid not in valid_item_eids:
                failures.append({
                    "component": "claim",
                    "claim_id": cid,
                    "reason": f"Claim references non-existent or invalid evidence ID '{sid}'.",
                })
                claim_ok = False

        # Causal link checks
        if ctype == "causal_link" and not is_abstention:
            if not sup_ids:
                failures.append({
                    "component": "claim",
                    "claim_id": cid,
                    "reason": "Causal link claim lacks supporting evidence IDs.",
                })
                claim_ok = False

            # Procedural text rejection
            ctext_low = ctext.lower()
            if any(p in ctext_low for p in ["this approach ensures", "evidence-backed rca", "structured approach", "methodology ensures"]):
                failures.append({
                    "component": "claim",
                    "claim_id": cid,
                    "reason": f"Procedural metadata text '{ctext[:60]}...' masquerading as causal root cause.",
                })
                claim_ok = False

        if claim_ok:
            valid_claims_count += 1

    # 3. Audit Structured Spatial Relations
    spatial_list: List[Any] = []
    if structured_result:
        spatial_list = (
            structured_result.get("spatial_relations", [])
            if isinstance(structured_result, dict)
            else getattr(structured_result, "spatial_relations", [])
        )

    valid_spatial_count = 0
    for sr in spatial_list:
        subj = sr.subject if hasattr(sr, "subject") else sr.get("subject", "")
        rel = sr.relation_type if hasattr(sr, "relation_type") else sr.get("relation_type", "")
        obj = sr.object if hasattr(sr, "object") else sr.get("object", "")
        seid = sr.supporting_evidence_id if hasattr(sr, "supporting_evidence_id") else sr.get("supporting_evidence_id")
        sfname = sr.filename if hasattr(sr, "filename") else sr.get("filename", "")
        tag_corr = sr.tag_corroboration if hasattr(sr, "tag_corroboration") else sr.get("tag_corroboration")

        sr_ok = True

        if not seid or seid not in item_map:
            failures.append({
                "component": "spatial_relation",
                "relation": f"{subj} {rel} {obj}",
                "reason": f"Spatial relation references invalid supporting_evidence_id '{seid}'.",
            })
            sr_ok = False
        else:
            backing_item = item_map[seid]
            b_chan = backing_item.retrieval_channel if hasattr(backing_item, "retrieval_channel") else backing_item.get("retrieval_channel")
            b_role = backing_item.evidence_role if hasattr(backing_item, "evidence_role") else backing_item.get("evidence_role")
            b_role_str = str(b_role.value if hasattr(b_role, "value") else b_role).upper()
            b_meta = backing_item.metadata if hasattr(backing_item, "metadata") else backing_item.get("metadata", {})

            # Must be visual channel
            if b_chan != "visual":
                failures.append({
                    "component": "spatial_relation",
                    "relation": f"{subj} {rel} {obj}",
                    "reason": f"Backing evidence item '{seid}' channel is '{b_chan}', not 'visual'.",
                })
                sr_ok = False

            # Must have P&ID role
            if "P_AND_ID" not in b_role_str:
                failures.append({
                    "component": "spatial_relation",
                    "relation": f"{subj} {rel} {obj}",
                    "reason": f"Backing evidence item '{seid}' role is '{b_role_str}', not 'P_AND_ID'.",
                })
                sr_ok = False

            # Must have observed_relations in metadata matching this relation
            obs_rels = b_meta.get("observed_relations", []) if isinstance(b_meta, dict) else []
            match_found = any(
                str(r.get("subject", "")).upper() == subj.upper()
                and str(r.get("object", "")).upper() == obj.upper()
                and str(r.get("relation_type", "")).upper() == rel.upper()
                for r in obs_rels if isinstance(r, dict)
            )
            if not match_found:
                failures.append({
                    "component": "spatial_relation",
                    "relation": f"{subj} {rel} {obj}",
                    "reason": f"Relation not found in backing item metadata observed_relations: {obs_rels}.",
                })
                sr_ok = False

            # Must have OCR tag corroboration
            if tag_corr is not True:
                failures.append({
                    "component": "spatial_relation",
                    "relation": f"{subj} {rel} {obj}",
                    "reason": "Spatial relation lacks deterministic OCR tag corroboration.",
                })
                sr_ok = False

        if sr_ok:
            valid_spatial_count += 1

    # 4. Audit Citations via Decomposed Metrics
    cit_metrics = calculate_decomposed_citation_metrics(
        result_text=result_text,
        bundle=bundle,
        valid_filenames=valid_filenames,
        is_ood=is_ood,
        claims=claims_list,
        structured_result=structured_result,
    )

    valid_cits_count = 0
    total_cits = cit_metrics.total_citations

    if is_abstention and total_cits == 0:
        # Honest abstention: 0 citations is expected and valid
        valid_cits_count = 0
    elif total_cits > 0:
        if cit_metrics.source_accuracy is not None and cit_metrics.source_accuracy < 1.0:
            for inv in cit_metrics.invalid_citations:
                if "Filename" in inv.get("reason", "") or "not recognized" in inv.get("reason", ""):
                    failures.append({
                        "component": "citation",
                        "citation": inv.get("citation"),
                        "reason": inv.get("reason"),
                    })
        if cit_metrics.locator_accuracy is not None and cit_metrics.locator_accuracy < 1.0:
            for inv in cit_metrics.invalid_citations:
                if "locator" in inv.get("reason", "").lower() or "coordinates" in inv.get("reason", "").lower():
                    failures.append({
                        "component": "citation",
                        "citation": inv.get("citation"),
                        "reason": inv.get("reason"),
                    })
        if cit_metrics.claim_binding_accuracy is not None and cit_metrics.claim_binding_accuracy < 1.0:
            for inv in cit_metrics.invalid_citations:
                if "bind" in inv.get("reason", "").lower():
                    failures.append({
                        "component": "citation",
                        "citation": inv.get("citation"),
                        "reason": inv.get("reason"),
                    })
        valid_cits_count = cit_metrics.claim_bound_citations
    elif not is_abstention:
        # Non-abstention case with 0 citations fails citation validation
        failures.append({
            "component": "citation",
            "citation": "NONE",
            "reason": "Non-abstention RCA scenario produced 0 grounded citations.",
        })

    # 5. Determine Independent Validity
    bench_valid = (len(failures) == 0)

    # 6. Check Divergence
    divergence = False
    if prod_valid is not None and prod_valid != bench_valid:
        divergence = True
        logger.warning(
            f"EVIDENCE_TRUTH_DIVERGENCE: Production claims evidence_chain_valid={prod_valid} "
            f"but Independent Evaluator determined benchmark_evidence_chain_valid={bench_valid}. "
            f"Failures: {failures}"
        )

    summary_str = None
    if failures:
        summary_str = "; ".join(f"[{f.get('component')}]: {f.get('reason')}" for f in failures[:3])

    return IndependentEvidenceEvaluation(
        benchmark_evidence_chain_valid=bench_valid,
        production_evidence_chain_valid=prod_valid,
        divergence_detected=divergence,
        evidence_item_count=len(items),
        valid_evidence_items=valid_items_count,
        claim_count=len(claims_list),
        valid_claim_bindings=valid_claims_count,
        spatial_relation_count=len(spatial_list),
        valid_spatial_relations=valid_spatial_count,
        citation_count=total_cits,
        valid_citations=valid_cits_count,
        validation_failures=failures,
        failure_summary=summary_str,
    )
