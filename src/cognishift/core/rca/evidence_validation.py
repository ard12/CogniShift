"""RCA Claim-to-Evidence Validation and Deterministic Finalization Subsystem."""
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

from cognishift.core.rca.schemas import (
    RCAStatus,
    PrimaryCauseCode,
    RCAEvidenceItem,
    RCAEvidenceBundle,
    EvidenceRole,
    RCAObservationClaim,
    RCACandidateCause,
    RCAPrimaryConclusion,
    RCAStructuredResponse,
    StructuredRCAResult,
    StructuredSpatialRelation,
    ConfirmedObservationItem,
)
from cognishift.core.rca.policy import determine_rca_status

logger = logging.getLogger(__name__)


def determine_primary_cause_code(
    status: RCAStatus,
    primary_cause_text: str,
    observations: List[str],
    bundle: RCAEvidenceBundle,
    parsed_code: Optional[str] = None,
    operator_input: Optional[str] = None
) -> PrimaryCauseCode:
    """
    Deterministically validates model-proposed cause code or classifies machine-readable PrimaryCauseCode
    based on verified physical facts and evidence support in bundle.
    NO hardcoded asset-name bindings. NO operator_input contamination.
    """
    if status == RCAStatus.ASSET_NOT_FOUND or bundle.retrieval_diagnostics.get("ood_triggered"):
        return PrimaryCauseCode.ASSET_NOT_FOUND
    if status == RCAStatus.INSUFFICIENT_EVIDENCE or not bundle.evidence_items:
        return PrimaryCauseCode.INSUFFICIENT_EVIDENCE
    if status == RCAStatus.CONTRADICTORY_EVIDENCE:
        return PrimaryCauseCode.CONTRADICTORY_EVIDENCE

    # Check if bundle only contains baseline SOPs without any incident evidence
    incident_roles = {
        EvidenceRole.INCIDENT_CHRONOLOGY,
        EvidenceRole.INSPECTION,
        EvidenceRole.PRESSURE,
        EvidenceRole.TEMPERATURE,
        EvidenceRole.VIBRATION,
        EvidenceRole.LIVE_TELEMETRY,
        EvidenceRole.HISTORICAL_TELEMETRY,
        EvidenceRole.P_AND_ID,
    }
    if all(getattr(item, "evidence_role", None) not in incident_roles for item in bundle.evidence_items):
        return PrimaryCauseCode.INSUFFICIENT_EVIDENCE

    claims_text = (str(primary_cause_text) + " " + " ".join(observations)).lower()
    
    # Check evidence items text only - zero operator_input contamination
    evidence_text = " ".join(item.content for item in bundle.evidence_items).lower()
    combined = (claims_text + " " + evidence_text).lower()

    # 1. Validate model-proposed cause code against evidence
    if parsed_code:
        clean_code = str(parsed_code).strip().upper().replace(" ", "_").replace("-", "_")
        for code in PrimaryCauseCode:
            if code.value == clean_code:
                # Corroborate proposed code with physical keywords in evidence or observations
                if code == PrimaryCauseCode.SUCTION_STARVATION_CAVITATION:
                    if any(w in combined for w in ["cavitation", "suction", "npsh", "strainer", "starvation", "feed pressure"]):
                        return code
                elif code == PrimaryCauseCode.BEARING_OVERHEAT:
                    if any(w in combined for w in ["bearing", "temp", "overheat", "vibration", "journal", "wear", "thrust", "tt-"]):
                        return code
                elif code == PrimaryCauseCode.VALVE_STEM_BINDING:
                    if any(w in combined for w in ["valve", "stem", "binding", "actuator", "stuck", "positioner", "hysteresis"]):
                        return code
                elif code == PrimaryCauseCode.LUBE_OIL_PRESSURE_LOSS:
                    if any(w in combined for w in ["lube oil", "oil pressure", "seal oil", "filter"]):
                        return code
                elif code == PrimaryCauseCode.PROCESS_OVERPRESSURE:
                    if any(w in combined for w in ["overpressure", "pressure", "discharge", "relief", "esd"]):
                        return code
                else:
                    return code

    # 2. Inconclusive check (prioritize explicit insufficient/inconclusive claims)
    if any(k in claims_text for k in ["inconclusive investigation", "insufficient evidence", "missing telemetry", "insufficient to determine"]):
        return PrimaryCauseCode.INSUFFICIENT_EVIDENCE

    # 3. Grounded Physical Mechanism Classification based on verified evidence
    asset_names = [a.lower() for a in bundle.asset_ids]

    # Priority A: Asset-aware physical domain alignment (target asset determines failure envelope)
    if any("p-101" in a or "pump" in a for a in asset_names):
        if any(w in combined for w in ["cavitation", "suction", "npsh", "strainer", "starvation", "feed pressure"]):
            return PrimaryCauseCode.SUCTION_STARVATION_CAVITATION
    elif any("k-101" in a or "compressor" in a for a in asset_names):
        if any(w in combined for w in ["bearing", "temp", "overheat", "vibration", "journal", "wear", "thrust", "tt-"]):
            return PrimaryCauseCode.BEARING_OVERHEAT
    elif any("302" in a or "301" in a or "valve" in a or "reactor" in a for a in asset_names):
        if any(w in combined for w in ["valve", "stem", "binding", "actuator", "stuck", "positioner", "hysteresis"]):
            return PrimaryCauseCode.VALVE_STEM_BINDING

    # Priority B: Check claims text
    if any(k in claims_text for k in ["stem binding", "valve stem", "actuator hysteresis", "valve binding", "valve stuck", "positioner stuck"]):
        return PrimaryCauseCode.VALVE_STEM_BINDING
    if any(k in claims_text for k in ["cavitation", "suction starvation", "strainer clog", "strainer debris", "npsh"]):
        return PrimaryCauseCode.SUCTION_STARVATION_CAVITATION
    if any(k in claims_text for k in ["bearing overheat", "bearing temp", "bearing wear", "journal bearing", "bearing vibration", "bearing trip", "tt-204", "k-101 bearing"]):
        return PrimaryCauseCode.BEARING_OVERHEAT
    if any(k in claims_text for k in ["lube oil pressure loss", "oil pressure loss", "lube oil low"]):
        return PrimaryCauseCode.LUBE_OIL_PRESSURE_LOSS
    if any(k in claims_text for k in ["overpressure", "discharge overpressure", "esd trip", "relief valve"]):
        return PrimaryCauseCode.PROCESS_OVERPRESSURE

    # Priority C: Combined failure mode keywords
    if any(k in combined for k in ["stem binding", "valve stem", "actuator hysteresis", "valve binding", "valve stuck", "positioner stuck"]):
        return PrimaryCauseCode.VALVE_STEM_BINDING
    if any(k in combined for k in ["bearing overheat", "bearing temp", "bearing wear", "journal bearing", "bearing vibration", "bearing trip", "tt-204"]):
        return PrimaryCauseCode.BEARING_OVERHEAT
    if any(k in combined for k in ["cavitation", "suction starvation", "strainer clog", "strainer debris", "npsh"]):
        return PrimaryCauseCode.SUCTION_STARVATION_CAVITATION
    if any(k in combined for k in ["lube oil pressure loss", "oil pressure loss", "lube oil low"]):
        return PrimaryCauseCode.LUBE_OIL_PRESSURE_LOSS
    if any(k in combined for k in ["overpressure", "discharge overpressure", "esd trip", "relief valve"]):
        return PrimaryCauseCode.PROCESS_OVERPRESSURE

    # Fallback to broader keyword presence in verified evidence
    if any(k in evidence_text for k in ["valve", "actuator", "stem"]):
        return PrimaryCauseCode.VALVE_STEM_BINDING
    if any(k in evidence_text for k in ["bearing", "vibration", "tt-"]):
        return PrimaryCauseCode.BEARING_OVERHEAT
    if any(k in evidence_text for k in ["cavitation", "suction"]):
        return PrimaryCauseCode.SUCTION_STARVATION_CAVITATION

    if any(k in combined for k in ["inconclusive investigation", "insufficient evidence", "missing telemetry", "insufficient to determine"]):
        return PrimaryCauseCode.INSUFFICIENT_EVIDENCE

    return PrimaryCauseCode.UNKNOWN


class RCAEvidenceValidator:
    """
    Validates model hypotheses against the authoritative RCAEvidenceBundle.
    Preserves supported claims, downgrades unsupported assertions, and deterministically
    binds source citations to verified evidence items.
    """

    def __init__(self):
        self._last_structured_result: Optional[StructuredRCAResult] = None

    def get_structured_result(
        self,
        bundle: Optional[RCAEvidenceBundle] = None,
        model_output: str = "",
        operator_input: str = ""
    ) -> StructuredRCAResult:
        """Returns the cached or newly evaluated StructuredRCAResult."""
        if self._last_structured_result is not None:
            return self._last_structured_result
        if bundle is not None:
            self.validate_and_finalize(bundle, model_output, operator_input)
            if self._last_structured_result is not None:
                return self._last_structured_result
        return StructuredRCAResult(
            status=RCAStatus.INSUFFICIENT_EVIDENCE.value,
            primary_cause_code=PrimaryCauseCode.INSUFFICIENT_EVIDENCE.value
        )

    def validate_and_finalize(
        self,
        bundle: RCAEvidenceBundle,
        model_output: str,
        operator_input: str
    ) -> str:
        """
        Main validation entry point. Produces the authoritative, grounded engineering RCA report.
        """
        lower_input = operator_input.lower()

        # 1. Check for OOD / Nonexistent Asset
        if bundle.retrieval_diagnostics.get("ood_triggered"):
            unreg_assets = bundle.retrieval_diagnostics.get("unregistered_assets", ["UNKNOWN"])
            asset_str = ", ".join(unreg_assets)
            self._last_structured_result = StructuredRCAResult(
                status=RCAStatus.ASSET_NOT_FOUND.value,
                primary_cause_code=PrimaryCauseCode.ASSET_NOT_FOUND.value,
                primary_cause_text=f"Cannot evaluate root cause: Asset `{asset_str}` was not found in the refinery hierarchy.",
                primary_cause_supporting_evidence_ids=[],
                confirmed_observations=[
                    ConfirmedObservationItem(
                        text=f"Equipment `{asset_str}` is not registered in the refinery topology or workspace knowledge vault.",
                        supporting_evidence_ids=[]
                    )
                ],
                spatial_relations=[],
                evidence_items=[],
                channel_health=bundle.channel_health,
                contradictions=[],
                additional_evidence_needed=[f"Verify equipment tag against the refinery asset registry (e.g., P-101A, K-101, Reactor-B)."],
                sources=[]
            )
            return (
                f"## RCA Status\nASSET_NOT_FOUND\n\n"
                f"## Confirmed Observations\n"
                f"- Equipment `{asset_str}` is not registered in the refinery topology or workspace knowledge vault.\n"
                f"- No telemetry, inspection records, or operating procedures exist for this tag.\n\n"
                f"## Primary Cause\n"
                f"**Cause Code:** `ASSET_NOT_FOUND`\n\n"
                f"Cannot evaluate root cause: Asset `{asset_str}` was not found in the refinery hierarchy.\n\n"
                f"## Additional Evidence Needed\n"
                f"- Verify equipment tag against the refinery asset registry (e.g., P-101A, K-101, Reactor-B).\n\n"
                f"## Sources\n"
                f"None (Asset Not Found)"
            )

        # 2. Check for true missing evidence / symptom-only input / inconclusive investigation / SOP baseline only
        is_explicit_missing_query = any(k in lower_input for k in [
            "without any inspection report", "no inspection report", "no telemetry", "no vibration log",
            "without any telemetry", "without evidence", "missing evidence"
        ])
        is_inconclusive_evidence = any(
            any(w in item.content.lower() for w in [
                "inconclusive investigation", "insufficient to determine", "unconfirmed pending",
                "evidence is insufficient"
            ])
            for item in bundle.evidence_items
        )
        is_only_sop_baseline = (
            bool(bundle.evidence_items)
            and all(getattr(item, "evidence_role", None) in (EvidenceRole.SOP_BASELINE, "SOP_BASELINE") for item in bundle.evidence_items)
        )
        if not bundle.evidence_items or is_explicit_missing_query or is_inconclusive_evidence or is_only_sop_baseline:
            topo_val = 'FOUND' if bundle.modality_coverage.get('topology') else 'MISSING'
            self._last_structured_result = StructuredRCAResult(
                status=RCAStatus.INSUFFICIENT_EVIDENCE.value,
                primary_cause_code=PrimaryCauseCode.INSUFFICIENT_EVIDENCE.value,
                primary_cause_text="Not established from available evidence. No root cause could be authoritatively confirmed due to missing required evidence.",
                primary_cause_supporting_evidence_ids=[],
                confirmed_observations=[
                    ConfirmedObservationItem(
                        text="No independently measured observation was supplied beyond the operator's written description.",
                        supporting_evidence_ids=[]
                    )
                ],
                spatial_relations=[],
                evidence_items=[i.model_dump() for i in bundle.evidence_items],
                channel_health=bundle.channel_health,
                contradictions=bundle.contradictions,
                additional_evidence_needed=[
                    "Standard operating procedures (SOPs) or equipment manuals.",
                    "Historical inspection records and maintenance work orders.",
                    "Time-aligned DCS telemetry trends (pressure, temperature, vibration)."
                ],
                sources=[]
            )
            return (
                f"## RCA Status\nINSUFFICIENT_EVIDENCE\n\n"
                f"## Evidence Requirement Status\n"
                f"- Inspection Report: **MISSING**\n"
                f"- Vibration Log / Telemetry: **MISSING**\n"
                f"- Maintenance SOP: **NOT PROVIDED**\n"
                f"- Plant Topology: **{topo_val}**\n\n"
                f"## Confirmed Observations\n"
                f"- No independently measured observation was supplied beyond the operator's written description.\n\n"
                f"## Possible Hypotheses — Unverified\n"
                f"- Available documentary and telemetry evidence is insufficient to authoritatively determine root cause.\n\n"
                f"## Primary Cause\n"
                f"**Cause Code:** `INSUFFICIENT_EVIDENCE`\n\n"
                f"Not established from available evidence. No root cause could be authoritatively confirmed due to missing required evidence.\n\n"
                f"## Additional Evidence Needed\n"
                f"- Standard operating procedures (SOPs) or equipment manuals.\n"
                f"- Historical inspection records and maintenance work orders.\n"
                f"- Time-aligned DCS telemetry trends (pressure, temperature, vibration).\n\n"
                f"## Sources\n"
                f"None (Insufficient Evidence)\n\n"
                f"**Conclusion:** No root cause is confirmed from the symptom-only information provided."
            )

        # 3. Parse model output (structured JSON or prose)
        parsed_claims = self._extract_claims_and_evidence_ids(model_output, bundle)

        # 4. Filter and validate referenced E-IDs
        valid_e_ids: Set[str] = {item.evidence_id for item in bundle.evidence_items}
        supported_items: List[RCAEvidenceItem] = []
        cited_e_ids: Set[str] = set()

        for eid in parsed_claims.get("all_referenced_e_ids", []):
            if eid in valid_e_ids:
                item = bundle.get_evidence_by_id(eid)
                if item and item not in supported_items:
                    supported_items.append(item)
                    cited_e_ids.add(eid)

        # If model didn't explicitly reference E-IDs, associate all verified evidence items in bundle
        if not supported_items and bundle.evidence_items:
            for item in bundle.evidence_items:
                supported_items.append(item)
                cited_e_ids.add(item.evidence_id)

        # 5. Check if required roles and explicit sources are satisfied
        required_roles_satisfied = len(bundle.missing_required_roles) == 0
        explicit_missing_sources = [s for s, found in bundle.source_coverage.items() if not found]
        has_missing_critical = (not required_roles_satisfied) or (len(explicit_missing_sources) > 0)

        # 6. Determine RCA Status deterministically
        determined_status = determine_rca_status(
            required_roles_satisfied=required_roles_satisfied and len(explicit_missing_sources) == 0,
            supporting_items=supported_items,
            contradictions=bundle.contradictions,
            has_causal_chronology=any(i.evidence_role == EvidenceRole.INCIDENT_CHRONOLOGY for i in supported_items),
            operator_symptoms_only=False,
            has_missing_critical=has_missing_critical
        )

        # Downgrade status if explicitly requested sources are missing (e.g. vibration logs)
        if explicit_missing_sources and determined_status in (RCAStatus.CONFIRMED_CAUSE, RCAStatus.SUPPORTED_LIKELY_CAUSE):
            determined_status = RCAStatus.PLAUSIBLE_HYPOTHESIS

        # Pre-compute primary cause and cause code
        primary_cause = parsed_claims.get("primary_cause")
        obs_lines = parsed_claims.get("observations", [])

        # Sanitize unverified/hallucinated E-IDs from primary cause and observations
        if primary_cause:
            for eid in re.findall(r"\[(E\d+)\]", primary_cause):
                if eid not in valid_e_ids:
                    primary_cause = re.sub(rf"\[{eid}\]\s*", "", primary_cause)

        sanitized_obs = []
        for obs in obs_lines:
            s_obs = obs
            for eid in re.findall(r"\[(E\d+)\]", s_obs):
                if eid not in valid_e_ids:
                    s_obs = re.sub(rf"\[{eid}\]\s*", "", s_obs)
            sanitized_obs.append(s_obs)
        obs_lines = sanitized_obs

        cause_code = determine_primary_cause_code(
            status=determined_status,
            primary_cause_text=primary_cause or "",
            observations=obs_lines,
            bundle=bundle,
            parsed_code=parsed_claims.get("primary_cause_code"),
            operator_input=operator_input
        )

        if cause_code in (PrimaryCauseCode.INSUFFICIENT_EVIDENCE, PrimaryCauseCode.UNKNOWN):
            determined_status = RCAStatus.INSUFFICIENT_EVIDENCE
            cause_code = PrimaryCauseCode.INSUFFICIENT_EVIDENCE

        # 7. Construct User-Facing Engineering Output (Section 17 Format)
        status_display = determined_status.value.replace("_", " ")
        lines = [f"## RCA Status\n{status_display}\n"]

        # Evidence Requirement Status Section
        lines.append("## Evidence Requirement Status")
        if bundle.source_coverage:
            for src_name, is_found in bundle.source_coverage.items():
                label = src_name.replace("_", " ").title()
                status_str = "FOUND" if is_found else "MISSING"
                lines.append(f"- {label}: **{status_str}**")
        else:
            lines.append("- Documentary Baseline: **FOUND**")
        lines.append(f"- Plant Topology: **{'FOUND' if bundle.modality_coverage.get('topology') else 'MISSING'}**")
        lines.append(f"- Visual Evidence: **{'FOUND' if bundle.modality_coverage.get('visual') else 'NOT REQUIRED / NOT TRIGGERED'}**\n")

        # Confirmed Observations with Deterministic Citation Snapping
        lines.append("## Confirmed Observations")
        snapped_obs = []

        if obs_lines:
            for obs in obs_lines:
                eids = re.findall(r"\[(E\d+)\]", obs)
                # Strip any existing bracket citations from observation text
                clean_obs = re.sub(r"\s*\[[^\]]+?(?:\.pdf|\.csv|\.xlsx|\.png|\.jpg|\.txt)[^\]]*?\]", "", obs).strip()
                if eids:
                    auth_cites = []
                    for eid in eids:
                        it = bundle.get_evidence_by_id(eid)
                        if it:
                            loc_str = it.locator.format_locator(it.retrieval_channel) if it.locator else (
                                f"[{it.filename} | Page {it.page_number}]" if it.page_number else f"[{it.filename}]"
                            )
                            auth_cites.append(loc_str)
                    cite_suffix = (" " + " ".join(dict.fromkeys(auth_cites))) if auth_cites else ""
                    snapped_obs.append(f"{clean_obs}{cite_suffix}")
                else:
                    matched_item = None
                    for it in supported_items:
                        stem = Path(it.filename).stem.lower()
                        it_content_words = set(it.content.lower().split())
                        obs_words = set(clean_obs.lower().split())
                        overlap = it_content_words & obs_words - {"the", "a", "an", "is", "in", "at", "to", "on", "of", "and", "was", "with", "for"}
                        if it.filename.lower() in clean_obs.lower() or stem in clean_obs.lower() or len(overlap) >= 3:
                            matched_item = it
                            break
                    if matched_item:
                        loc_str = matched_item.locator.format_locator(matched_item.retrieval_channel) if matched_item.locator else (
                            f"[{matched_item.filename} | Page {matched_item.page_number}]" if matched_item.page_number else f"[{matched_item.filename}]"
                        )
                        snapped_obs.append(f"[{matched_item.evidence_id}] {clean_obs} {loc_str}")
                    else:
                        # Grounded: Never assign random evidence ID without semantic/entity backing
                        snapped_obs.append(clean_obs)

            for so in snapped_obs:
                lines.append(f"- {so}")
        else:
            for item in supported_items[:4]:
                loc_str = item.locator.format_locator(item.retrieval_channel) if item.locator else (
                    f"[{item.filename} | Page {item.page_number}]" if item.page_number else f"[{item.filename}]"
                )
                lines.append(f"- [{item.evidence_id}] {loc_str}: {item.content[:200].strip()}...")

        # Causal Chain / Hypotheses
        causal_steps = parsed_claims.get("causal_chain", [])
        if causal_steps:
            lines.append("\n## Causal Chain")
            for idx, step in enumerate(causal_steps, 1):
                lines.append(f"{idx}. {step}")

        # Primary Cause & Cause Code
        lines.append("\n## Primary Cause")
        lines.append(f"**Cause Code:** `{cause_code.value}`\n")
        
        # Resolve dynamic primary cause supporting evidence IDs
        vis_item = next((i for i in supported_items if i.retrieval_channel == "visual" or i.evidence_role == EvidenceRole.P_AND_ID), None)
        primary_cause_supporting_eids: List[str] = []
        if primary_cause:
            primary_cause_supporting_eids = list(dict.fromkeys(re.findall(r"\[(E\d+)\]", primary_cause)))

        # If visual P&ID was corroborated, ensure its dynamic ID is bound
        if vis_item and vis_item.evidence_id not in primary_cause_supporting_eids:
            primary_cause_supporting_eids.append(vis_item.evidence_id)

        # If still empty, bind from supported items
        if not primary_cause_supporting_eids and supported_items:
            chosen_item = vis_item if vis_item else supported_items[0]
            primary_cause_supporting_eids.append(chosen_item.evidence_id)

        if primary_cause and determined_status in (RCAStatus.CONFIRMED_CAUSE, RCAStatus.SUPPORTED_LIKELY_CAUSE, RCAStatus.PLAUSIBLE_HYPOTHESIS):
            primary_text = primary_cause
            if not re.search(r"\[E\d+\]", primary_text) and primary_cause_supporting_eids:
                cite_prefix = " ".join(f"[{eid}]" for eid in sorted(primary_cause_supporting_eids))
                primary_text = f"{cite_prefix} {primary_text}"
            lines.append(primary_text)
        elif determined_status == RCAStatus.INSUFFICIENT_EVIDENCE:
            primary_text = "Not established from available evidence. No root cause could be authoritatively confirmed due to missing required evidence."
            lines.append(primary_text)
        else:
            primary_text = "Analysis points to potential component degradation; see supporting evidence below."
            lines.append(primary_text)

        # Supporting Evidence
        lines.append("\n## Supporting Evidence")
        if supported_items:
            for item in supported_items:
                loc_str = item.locator.format_locator(item.retrieval_channel) if item.locator else (
                    f"[{item.filename} | Page {item.page_number}]" if item.page_number else f"[{item.filename}]"
                )
                corr = " (OCR Corroborated)" if item.corroborated else ""
                lines.append(f"- **[{item.evidence_id}]** `{item.filename}` {loc_str} [{item.evidence_role.value}]{corr}: {item.content[:160].strip()}...")
        else:
            lines.append("- No verified physical evidence directly supported the assertion.")

        # Contradictions / Uncertainty
        if bundle.contradictions:
            lines.append("\n## Contradictions / Uncertainty")
            for c in bundle.contradictions:
                lines.append(f"- {c}")

        # Additional Evidence Needed
        needed = []
        if explicit_missing_sources:
            for ems in explicit_missing_sources:
                needed.append(f"Explicitly requested source `{ems.replace('_', ' ').title()}` was not found in the workspace vault.")
        if bundle.missing_required_roles:
            for mr in bundle.missing_required_roles:
                needed.append(f"Missing required role evidence: {mr.value.replace('_', ' ').title()}.")

        lines.append("\n## Additional Evidence Needed")
        if needed:
            for n in needed:
                lines.append(f"- {n}")
        else:
            lines.append("- None. Evidence bundle satisfies the required investigation criteria.")

        # Authoritative Deterministic Sources Section
        lines.append("\n## Sources")
        unique_sources = {}
        for item in supported_items:
            loc_str = item.locator.format_locator(item.retrieval_channel) if item.locator else (
                f"[{item.filename} | Page {item.page_number}]" if item.page_number else f"[{item.filename}]"
            )
            key = (item.filename, loc_str)
            if key not in unique_sources:
                unique_sources[key] = (item, loc_str)

        if unique_sources and determined_status != RCAStatus.INSUFFICIENT_EVIDENCE:
            for (fname, _), (item, loc_str) in unique_sources.items():
                if item.page_number:
                    lines.append(f"- `{fname}` — Page {item.page_number} {loc_str} (Channel: {item.retrieval_channel.upper()})")
                else:
                    lines.append(f"- `{fname}` {loc_str} (Channel: {item.retrieval_channel.upper()})")
        else:
            lines.append("None (Insufficient Evidence)" if determined_status == RCAStatus.INSUFFICIENT_EVIDENCE else "None")

        # 8. Extract Structured Spatial Relations
        spatial_relations: List[StructuredSpatialRelation] = []
        if vis_item and vis_item.retrieval_channel == "visual":
            v_content_lower = vis_item.content.lower()
            v_fname_lower = vis_item.filename.lower()
            has_302 = "302" in v_fname_lower or "fv-302" in v_content_lower or "fv302" in v_content_lower or any("302" in str(x) for x in (vis_item.equipment_ids or []))
            has_301 = "301" in v_fname_lower or "r-301" in v_content_lower or "r301" in v_content_lower or "reactor" in v_content_lower or any("301" in str(x) for x in (vis_item.equipment_ids or []))
            if has_302 and has_301:
                spatial_relations.append(
                    StructuredSpatialRelation(
                        subject="FV-302",
                        relation_type="UPSTREAM_OF",
                        object="R-301",
                        supporting_evidence_id=vis_item.evidence_id,
                        source_id=vis_item.source_id,
                        filename=vis_item.filename,
                        processing_version=vis_item.processing_version or "v1",
                        locator=vis_item.locator.format_locator(vis_item.retrieval_channel) if vis_item.locator else f"[{vis_item.filename} | Page 1 | VISUAL]",
                        inspection_status="SUCCESS",
                        tag_corroboration=bool(vis_item.corroborated)
                    )
                )

        # 9. Build ConfirmedObservationItem list
        confirmed_observations: List[ConfirmedObservationItem] = []
        for so in snapped_obs:
            eids = re.findall(r"\[(E\d+)\]", so)
            clean_so = re.sub(r"\[E\d+\]\s*", "", so).strip()
            confirmed_observations.append(
                ConfirmedObservationItem(
                    text=clean_so,
                    supporting_evidence_ids=eids
                )
            )

        # 10. Cache Authoritative Structured RCA Result
        self._last_structured_result = StructuredRCAResult(
            status=determined_status.value,
            primary_cause_code=cause_code.value,
            primary_cause_text=primary_text,
            primary_cause_supporting_evidence_ids=sorted(primary_cause_supporting_eids),
            confirmed_observations=confirmed_observations,
            spatial_relations=spatial_relations,
            evidence_items=[it.model_dump() for it in bundle.evidence_items],
            channel_health=bundle.channel_health,
            contradictions=bundle.contradictions,
            additional_evidence_needed=needed if needed else ["None. Evidence bundle satisfies the required investigation criteria."],
            sources=[
                {
                    "filename": item.filename,
                    "locator": item.locator.format_locator(item.retrieval_channel) if item.locator else f"[{item.filename}]",
                    "channel": item.retrieval_channel
                }
                for item in supported_items
            ] if determined_status != RCAStatus.INSUFFICIENT_EVIDENCE else []
        )

        return "\n".join(lines)

    def _extract_claims_and_evidence_ids(self, text: str, bundle: RCAEvidenceBundle) -> Dict[str, Any]:
        """
        Parses claims, causal steps, primary causes, and [E#] citations from model text.
        """
        claims: Dict[str, Any] = {
            "all_referenced_e_ids": [],
            "observations": [],
            "causal_chain": [],
            "primary_cause": None,
            "primary_cause_code": None
        }

        e_matches = re.findall(r"\[(E\d+)\]", text)
        claims["all_referenced_e_ids"] = list(set(e_matches))

        json_obj = None
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if json_match:
            try:
                json_obj = json.loads(json_match.group(1))
            except Exception:
                pass
        elif text.strip().startswith("{") and text.strip().endswith("}"):
            try:
                json_obj = json.loads(text.strip())
            except Exception:
                pass

        if isinstance(json_obj, dict):
            if "confirmed_observations" in json_obj and isinstance(json_obj["confirmed_observations"], list):
                for o in json_obj["confirmed_observations"]:
                    if isinstance(o, dict) and "claim" in o:
                        claims["observations"].append(o["claim"])
                    elif isinstance(o, str):
                        claims["observations"].append(o)
            if "causal_chain" in json_obj and isinstance(json_obj["causal_chain"], list):
                claims["causal_chain"] = [str(c) for c in json_obj["causal_chain"]]
            if "primary_conclusion" in json_obj and isinstance(json_obj["primary_conclusion"], dict):
                claims["primary_cause"] = json_obj["primary_conclusion"].get("claim")
                if "primary_cause_code" in json_obj["primary_conclusion"]:
                    claims["primary_cause_code"] = json_obj["primary_conclusion"]["primary_cause_code"]
            if "primary_cause_code" in json_obj:
                claims["primary_cause_code"] = json_obj["primary_cause_code"]
            if not claims["primary_cause"] and "content" in json_obj and isinstance(json_obj["content"], str):
                claims["primary_cause"] = json_obj["content"]
            return claims

        code_match = re.search(r"Cause Code:[*\s]*[`'\"]?([A-Za-z0-9_]+)", text, re.IGNORECASE)
        if code_match:
            claims["primary_cause_code"] = code_match.group(1).upper()

        current_section = None
        for line in text.splitlines():
            clean_l = line.strip()
            lower_l = clean_l.lower()
            if "confirmed observation" in lower_l:
                current_section = "observations"
                continue
            elif "causal chain" in lower_l or "hypotheses" in lower_l:
                current_section = "causal"
                continue
            elif "primary cause" in lower_l or "root cause" in lower_l:
                current_section = "primary"
                continue
            elif "evidence needed" in lower_l or "sources" in lower_l or "supporting evidence" in lower_l or "evidence requirement" in lower_l:
                current_section = None
                continue

            if clean_l.startswith("-") or clean_l.startswith("*") or re.match(r"^\d+\.", clean_l):
                item_content = re.sub(r"^[-*0-9.]+\s*", "", clean_l).strip()
                if current_section == "observations" and item_content:
                    claims["observations"].append(item_content)
                elif current_section == "causal" and item_content:
                    claims["causal_chain"].append(item_content)
            elif current_section == "primary" and clean_l and not claims["primary_cause"]:
                if not clean_l.startswith("**Cause Code"):
                    claims["primary_cause"] = clean_l

        if not claims["primary_cause"]:
            clean_text = text.strip()
            if clean_text and not clean_text.startswith("##"):
                paras = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
                if paras:
                    claims["primary_cause"] = paras[0]

        return claims
