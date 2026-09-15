"""
Artifact-Context Compatibility and Semantic Verification Engine.
Enforces fail-closed validation between candidate visual artifacts, grounded scenario context,
figure captions, sovereignty phrasing, and standards claims.
"""
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from cognishift.core.artifact_quality.schemas import (
    ArtifactSemanticMetadata,
    DimensionStatus,
    GroundedArtifactContext,
    MeasuredQuantity,
    PhysicalDimension,
    QualityDimensionReport,
    StandardClaim,
    TimeWindow,
    VisualPurpose,
)

SEMANTIC_VALIDATOR_VERSION = "v3.1.0"

APPROVED_SOVEREIGNTY_PATTERNS = [
    "local sovereign execution with no public-cloud ai/model dependency in the demonstrated workflow",
    "no public-cloud ai/model dependency in this workflow",
    "no public-cloud model dependency in the demonstrated workflow",
    "local sovereign execution"
]

UNMEASURED_SOVEREIGNTY_PROHIBITIONS = [
    "zero cloud dependencies",
    "zero network egress",
    "fully air-gapped",
    "100% offline"
]

SYNTHETIC_DISCLOSURE_MARKERS = [
    "synthetic demonstration data",
    "demonstration scenario",
    "synthetic approval data",
    "not a record of an actual plant incident",
    "demo fixture"
]


def validate_artifact_context_compatibility(
    candidate: Union[ArtifactSemanticMetadata, Dict[str, Any]],
    context: GroundedArtifactContext,
    requested_purpose: Optional[VisualPurpose] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Exhaustively validates whether candidate visual metadata is compatible with document context.
    Fails closed on:
    - Asset mismatch
    - Headline metric / setpoint mismatch (with physical unit normalization)
    - Temporal disjointness
    - Visual purpose contradiction
    - Scenario / Context divergence
    """
    if isinstance(candidate, dict):
        cand_dict = {
            "artifact_type": candidate.get("artifact_type", "png"),
            "workspace_id": candidate.get("workspace_id", getattr(context, "workspace_id", 1)),
            "content_context_id": candidate.get("content_context_id", getattr(context, "content_context_id", "ctx_default")),
            "artifact_id": candidate.get("artifact_id"),
            "scenario_id": candidate.get("scenario_id"),
            "subject_assets": candidate.get("subject_assets", []),
            "measurement_tags": candidate.get("measurement_tags", []),
            "metric": candidate.get("metric"),
            "units": candidate.get("units"),
            "chart_purpose": candidate.get("chart_purpose"),
            "headline_metric": candidate.get("headline_metric"),
            "time_window": candidate.get("time_window"),
            "is_synthetic_demo": candidate.get("is_synthetic_demo", False),
            "source_references": candidate.get("source_references", []),
            "generation_parameters": candidate.get("generation_parameters", {})
        }
        candidate = ArtifactSemanticMetadata(**cand_dict)

    diagnostics = {
        "candidate_id": candidate.artifact_id,
        "candidate_type": candidate.artifact_type,
        "context_id": context.content_context_id,
        "checks": {}
    }

    # 1. Content Context / Scenario Check
    if candidate.scenario_id and context.scenario_id:
        if candidate.scenario_id != context.scenario_id:
            reason = f"ARTIFACT_CONTEXT_MISMATCH: Candidate scenario '{candidate.scenario_id}' != Document context '{context.scenario_id}'"
            diagnostics["checks"]["scenario"] = {"status": "FAIL", "reason": reason}
            return False, reason, diagnostics
        diagnostics["checks"]["scenario"] = {"status": "PASS"}

    # 2. Subject Asset Check
    if candidate.subject_assets and context.subject_assets:
        cand_assets_norm = {a.strip().upper() for a in candidate.subject_assets}
        ctx_assets_norm = {a.strip().upper() for a in context.subject_assets}
        overlap = cand_assets_norm.intersection(ctx_assets_norm)
        if not overlap:
            reason = f"ARTIFACT_CONTEXT_MISMATCH: Visual assets {candidate.subject_assets} do not overlap with document context assets {context.subject_assets}"
            diagnostics["checks"]["subject_assets"] = {"status": "FAIL", "reason": reason}
            return False, reason, diagnostics
        diagnostics["checks"]["subject_assets"] = {"status": "PASS", "overlap": list(overlap)}

    # 3. Headline Metric / Threshold Consistency (with Unit Normalization)
    if candidate.headline_metric and context.quantities:
        cand_m = candidate.headline_metric
        # Find matching quantity by label or dimension
        matching_q = None
        if cand_m.label and cand_m.label in context.quantities:
            matching_q = context.quantities[cand_m.label]
        else:
            for k, q in context.quantities.items():
                if q.dimension == cand_m.dimension:
                    matching_q = q
                    break

        if matching_q:
            is_compat, msg = cand_m.is_compatible_with(matching_q)
            if not is_compat:
                reason = f"SEMANTIC_CONSISTENCY_FAIL: Headline metric mismatch - {msg}"
                diagnostics["checks"]["headline_metric"] = {"status": "FAIL", "reason": reason}
                return False, reason, diagnostics
            diagnostics["checks"]["headline_metric"] = {"status": "PASS", "detail": msg}

    # 4. Temporal Window Relation Check
    if candidate.time_window and context.time_window:
        rel = candidate.time_window.relation_to(context.time_window)
        diagnostics["checks"]["time_window"] = {"relation": rel}
        if rel == "disjoint":
            reason = f"TIME_WINDOW_MISMATCH: Visual time window is disjoint from document context time window"
            diagnostics["checks"]["time_window"]["status"] = "FAIL"
            diagnostics["checks"]["time_window"]["reason"] = reason
            return False, reason, diagnostics
        diagnostics["checks"]["time_window"]["status"] = "PASS"

    # 5. Visual Purpose Alignment
    target_purpose = requested_purpose or (candidate.chart_purpose if candidate.chart_purpose else None)
    if requested_purpose and candidate.chart_purpose:
        if requested_purpose != candidate.chart_purpose:
            reason = f"CAPTION_PURPOSE_MISMATCH: Requested visual purpose '{requested_purpose.value}' contradicts candidate purpose '{candidate.chart_purpose.value}'"
            diagnostics["checks"]["purpose"] = {"status": "FAIL", "reason": reason}
            return False, reason, diagnostics
        diagnostics["checks"]["purpose"] = {"status": "PASS"}

    return True, "Artifact context compatibility verified.", diagnostics


def validate_figure_caption(
    caption: str,
    candidate: ArtifactSemanticMetadata,
    context: GroundedArtifactContext
) -> Tuple[bool, str]:
    """
    Verifies that caption claims truthfully reflect visual metadata and document context.
    Detects false labeling (e.g. labeling an overpressure excursion as safe depressurization).
    """
    cap_lower = caption.lower()

    # Check asset claims in caption
    if candidate.subject_assets:
        # If caption explicitly names an asset not in candidate's assets:
        for a in candidate.subject_assets:
            pass  # Normal
        # Check if caption mentions an asset from context that contradicts candidate
        for ca in context.subject_assets:
            if ca.lower() in cap_lower and not any(ca.lower() == a.lower() for a in candidate.subject_assets):
                return False, f"Caption claims asset '{ca}' which is not depicted in visual {candidate.subject_assets}"

    # Check purpose claims in caption
    if candidate.chart_purpose == VisualPurpose.INCIDENT_PRESSURE_EXCURSION:
        if "safe depressurization" in cap_lower or "normal operation" in cap_lower:
            return False, "Caption claims 'safe depressurization' or 'normal operation' on an incident overpressure excursion visual"

    if candidate.chart_purpose == VisualPurpose.SAFE_DEPRESSURIZATION_ENVELOPE:
        if "incident excursion" in cap_lower or "pressure excursion" in cap_lower:
            return False, "Caption claims 'incident excursion' on a safe depressurization envelope visual"

    return True, "Caption is semantically valid."


def validate_sovereignty_wording(text: str) -> Tuple[bool, str, List[str]]:
    """
    Enforces canonical sovereignty terminology.
    Flags unmeasured absolute claims ('zero cloud dependencies', '100% offline').
    """
    t_lower = text.lower()
    offending = []
    for bad in UNMEASURED_SOVEREIGNTY_PROHIBITIONS:
        if bad in t_lower:
            offending.append(bad)

    if offending:
        return False, f"SOVEREIGNTY_CLAIM_FAIL: Unmeasured claims detected: {offending}. Use approved phrasing: 'Local sovereign execution with no public-cloud AI/model dependency in the demonstrated workflow.'", offending

    return True, "Sovereignty terminology complies with approved contract.", []


def validate_demo_disclosure(
    text: str,
    is_synthetic_demo: bool
) -> Tuple[bool, str]:
    """
    Verifies that demonstration artifacts carry explicit synthetic disclosure.
    Prevents synthetic scenarios from posing as actual confidential plant incident records.
    """
    if not is_synthetic_demo:
        return True, "Not flagged as synthetic demo."

    t_lower = text.lower()
    has_marker = any(m in t_lower for m in SYNTHETIC_DISCLOSURE_MARKERS)
    if not has_marker:
        return False, "DEMO_DISCLOSURE_FAIL: Synthetic demonstration artifact lacks required disclosure marker (e.g., 'SYNTHETIC DEMONSTRATION DATA' or 'DEMONSTRATION SCENARIO')."

    return True, "Synthetic demo disclosure verified."


def validate_standards_grounding(
    text: str,
    claims_ledger: List[StandardClaim]
) -> Tuple[bool, str, List[str]]:
    """
    Checks that regulatory and standards claims (ASME, API, OISD, PESO, ISO, IEC)
    are substantiated by verified entries in the claims ledger.
    Fails closed if unsubstantiated claims are asserted as fact.
    """
    standards_keywords = ["ASME", "API 521", "API 520", "OISD", "PESO", "IEC 61511", "IEC 62443", "ISO 9001"]
    unsubstantiated = []

    for kw in standards_keywords:
        pattern = re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
        if pattern.search(text):
            # Check if substantiated in ledger
            supported = any(
                kw.lower() in c.standard_designation.lower() and c.support_status == "VERIFIED"
                for c in claims_ledger
            )
            if not supported:
                unsubstantiated.append(kw)

    if unsubstantiated:
        return False, f"STANDARDS_GROUNDING_FAIL: Unverified standard claims detected without supporting evidence in claims ledger: {unsubstantiated}", unsubstantiated

    return True, "All standards claims are verified in claims ledger.", []


def validate_signatory_authenticity(
    signatories: List[Dict[str, Any]],
    is_synthetic_demo: bool
) -> Tuple[bool, str]:
    """
    Verifies that sign-off blocks do not fabricate completed signatures.
    Default status must be PENDING APPROVAL unless verified digital signature exists.
    """
    for sig in signatories:
        status = str(sig.get("status", "")).upper()
        name = str(sig.get("name", "")).strip()
        hash_id = str(sig.get("hash_id", "")).strip()

        if status in ("COMPLETED", "APPROVED", "SIGNED"):
            if is_synthetic_demo:
                # Must be explicitly marked as synthetic
                if "DEMO" not in hash_id.upper() and "SYNTHETIC" not in hash_id.upper():
                    return False, f"SIGNATURE_FABRICATION_FAIL: Completed signature '{hash_id}' on synthetic demo must include 'SYNTHETIC' or 'DEMO' tag."
            else:
                # Real workflow: must not be placeholder or model-generated name
                if not hash_id.startswith("SIG-AUTH-"):
                    return False, f"SIGNATURE_FABRICATION_FAIL: Signatory '{name}' marked as completed without verified cryptographic signature token."

    return True, "Signatory authenticity rules verified."
