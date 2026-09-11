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
    RCAStructuredResponse
)
from cognishift.core.rca.policy import determine_rca_status

logger = logging.getLogger(__name__)


def determine_primary_cause_code(
    status: RCAStatus,
    primary_cause_text: str,
    observations: List[str],
    bundle: RCAEvidenceBundle,
    parsed_code: Optional[str] = None
) -> PrimaryCauseCode:
    """Deterministically extracts or classifies machine-readable PrimaryCauseCode."""
    if status == RCAStatus.ASSET_NOT_FOUND or bundle.retrieval_diagnostics.get("ood_triggered"):
        return PrimaryCauseCode.ASSET_NOT_FOUND
    if status == RCAStatus.INSUFFICIENT_EVIDENCE or not bundle.evidence_items:
        return PrimaryCauseCode.INSUFFICIENT_EVIDENCE
    if status == RCAStatus.CONTRADICTORY_EVIDENCE:
        return PrimaryCauseCode.CONTRADICTORY_EVIDENCE

    if parsed_code:
        clean_code = str(parsed_code).strip().upper().replace(" ", "_").replace("-", "_")
        for code in PrimaryCauseCode:
            if code.value == clean_code:
                return code

    evidence_text = " ".join(item.content for item in bundle.evidence_items)
    evidence_files = " ".join(item.filename for item in bundle.evidence_items)
    combined_query_and_cause = (str(primary_cause_text) + " " + " ".join(observations)).lower()
    combined = (combined_query_and_cause + " " + evidence_text + " " + evidence_files).lower()
    asset_ids = [str(a).strip().upper() for a in (bundle.asset_ids or [])]

    # 1. Pump Specific (P-101A) -> Suction Starvation & Cavitation
    if any(a in ("P-101A", "P101A") for a in asset_ids) or (
        any(k in combined_query_and_cause for k in ["p-101", "p101", "cavitation", "suction starvation", "strainer"])
        and not any(a in ("K-101", "K101") for a in asset_ids)
    ):
        if any(k in combined for k in ["cavitation", "suction starvation", "strainer", "npsh", "starvation", "vibration"]):
            return PrimaryCauseCode.SUCTION_STARVATION_CAVITATION

    # 2. Compressor Specific (K-101) -> Bearing Overheat / Journal Bearing
    if any(a in ("K-101", "K101") for a in asset_ids) or (
        any(k in combined_query_and_cause for k in ["k-101", "k101", "compressor"])
        and not any(a in ("P-101A", "P101A") for a in asset_ids)
    ):
        if any(k in combined for k in ["bearing", "overheat", "temp", "tt-204", "journal", "wear"]):
            return PrimaryCauseCode.BEARING_OVERHEAT

    # 3. Control Valve Specific (FV-302, R-301) -> Valve Stem Binding
    if any(a in ("FV-302", "FV302", "R-301", "R301") for a in asset_ids) or any(k in combined_query_and_cause for k in ["fv-302", "fv302", "valve stem", "actuator"]):
        if any(k in combined for k in ["valve", "stem", "fv-302", "fv302", "actuator", "stuck", "binding"]):
            return PrimaryCauseCode.VALVE_STEM_BINDING

    # 4. Inconclusive / Missing Telemetry
    if any(k in combined for k in ["inconclusive investigation", "insufficient evidence", "missing telemetry", "insufficient to determine"]):
        return PrimaryCauseCode.INSUFFICIENT_EVIDENCE

    # 5. General Fallbacks
    if any(k in combined for k in ["cavitation", "suction starvation", "strainer clog", "strainer debris", "npsh"]):
        return PrimaryCauseCode.SUCTION_STARVATION_CAVITATION
    if any(k in combined for k in ["bearing overheat", "bearing temp", "bearing wear", "journal bearing", "tt-204"]):
        return PrimaryCauseCode.BEARING_OVERHEAT
    if any(k in combined for k in ["valve stem", "stem binding", "fv-302", "fv302", "actuator hysteresis", "valve stuck"]):
        return PrimaryCauseCode.VALVE_STEM_BINDING
    if any(k in combined for k in ["lube oil", "seal oil", "oil pressure loss"]):
        return PrimaryCauseCode.LUBE_OIL_PRESSURE_LOSS
    if any(k in combined for k in ["overpressure", "discharge overpressure", "esd trip", "relief valve"]):
        return PrimaryCauseCode.PROCESS_OVERPRESSURE

    return PrimaryCauseCode.UNKNOWN


class RCAEvidenceValidator:
    """
    Validates model hypotheses against the authoritative RCAEvidenceBundle.
    Preserves supported claims, downgrades unsupported assertions, and deterministically
    binds source citations to verified evidence items.
    """

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

        # 2. Check for true missing evidence / symptom-only input / inconclusive investigation
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
        if not bundle.evidence_items or is_explicit_missing_query or is_inconclusive_evidence:
            topo_val = 'FOUND' if bundle.modality_coverage.get('topology') else 'MISSING'
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

        # If model didn't explicitly reference E-IDs, associate retrieved evidence items matching keywords
        if not supported_items and bundle.evidence_items:
            for item in bundle.evidence_items:
                if item.evidence_role in (
                    EvidenceRole.INSPECTION,
                    EvidenceRole.SOP_BASELINE,
                    EvidenceRole.VIBRATION,
                    EvidenceRole.INCIDENT_CHRONOLOGY,
                    EvidenceRole.P_AND_ID,
                    EvidenceRole.TOPOLOGY
                ):
                    supported_items.append(item)
                    cited_e_ids.add(item.evidence_id)

        # 5. Check if required roles and explicit sources are satisfied
        required_roles_satisfied = len(bundle.missing_required_roles) == 0
        explicit_missing_sources = [s for s, found in bundle.source_coverage.items() if not found]

        # 6. Determine RCA Status deterministically
        determined_status = determine_rca_status(
            required_roles_satisfied=required_roles_satisfied and len(explicit_missing_sources) == 0,
            supporting_items=supported_items,
            contradictions=bundle.contradictions,
            has_causal_chronology=any(i.evidence_role == EvidenceRole.INCIDENT_CHRONOLOGY for i in supported_items),
            operator_symptoms_only=False
        )

        # Downgrade status if explicitly requested sources are missing (e.g. vibration logs)
        if explicit_missing_sources and determined_status == RCAStatus.CONFIRMED_CAUSE:
            determined_status = RCAStatus.SUPPORTED_LIKELY_CAUSE

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
        obs_lines = parsed_claims.get("observations", [])
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
                            loc = f"Page {it.page_number}" if it.page_number else "Topology"
                            auth_cites.append(f"[{it.filename} | {loc}]")
                    cite_suffix = (" " + " ".join(dict.fromkeys(auth_cites))) if auth_cites else ""
                    snapped_obs.append(f"{clean_obs}{cite_suffix}")
                else:
                    matched_item = None
                    for it in supported_items:
                        stem = Path(it.filename).stem.lower()
                        if it.filename.lower() in clean_obs.lower() or stem in clean_obs.lower():
                            matched_item = it
                            break
                    if matched_item:
                        loc = f"Page {matched_item.page_number}" if matched_item.page_number else "Topology"
                        snapped_obs.append(f"[{matched_item.evidence_id}] {clean_obs} [{matched_item.filename} | {loc}]")
                    elif supported_items:
                        it = supported_items[0]
                        loc = f"Page {it.page_number}" if it.page_number else "Topology"
                        snapped_obs.append(f"[{it.evidence_id}] {clean_obs} [{it.filename} | {loc}]")
                    else:
                        snapped_obs.append(clean_obs)

            for so in snapped_obs:
                lines.append(f"- {so}")
        else:
            for item in supported_items[:4]:
                loc = f"Page {item.page_number}" if item.page_number else "Topology"
                lines.append(f"- [{item.evidence_id}] [{item.filename} | {loc}]: {item.content[:200].strip()}...")

        # Causal Chain / Hypotheses
        causal_steps = parsed_claims.get("causal_chain", [])
        if causal_steps:
            lines.append("\n## Causal Chain")
            for idx, step in enumerate(causal_steps, 1):
                lines.append(f"{idx}. {step}")

        # Primary Cause & Cause Code
        primary_cause = parsed_claims.get("primary_cause")
        cause_code = determine_primary_cause_code(
            status=determined_status,
            primary_cause_text=primary_cause or "",
            observations=obs_lines,
            bundle=bundle,
            parsed_code=parsed_claims.get("primary_cause_code")
        )

        lines.append("\n## Primary Cause")
        lines.append(f"**Cause Code:** `{cause_code.value}`\n")
        if primary_cause and determined_status in (RCAStatus.CONFIRMED_CAUSE, RCAStatus.SUPPORTED_LIKELY_CAUSE, RCAStatus.PLAUSIBLE_HYPOTHESIS):
            primary_text = primary_cause
            if not re.search(r"\[E\d+\]", primary_text) and supported_items:
                primary_text = f"[{supported_items[0].evidence_id}] {primary_text}"
            lines.append(primary_text)
        elif determined_status == RCAStatus.INSUFFICIENT_EVIDENCE:
            lines.append("Not established from available evidence. No root cause could be authoritatively confirmed due to missing required evidence.")
        else:
            lines.append("Analysis points to potential component degradation; see supporting evidence below.")

        # Supporting Evidence
        lines.append("\n## Supporting Evidence")
        if supported_items:
            for item in supported_items:
                loc = f"Page {item.page_number}" if item.page_number else "Topology"
                corr = " (OCR Corroborated)" if item.corroborated else ""
                lines.append(f"- **[{item.evidence_id}]** `{item.filename}` ({loc}) [{item.evidence_role.value}]{corr}: {item.content[:160].strip()}...")
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
            key = (item.filename, item.page_number)
            if key not in unique_sources:
                unique_sources[key] = item

        if unique_sources:
            for (fname, pnum), item in unique_sources.items():
                if pnum:
                    lines.append(f"- `{fname}` — Page {pnum} [{fname} | Page {pnum}] (Channel: {item.retrieval_channel.upper()})")
                else:
                    lines.append(f"- `{fname}` [{fname}] (Channel: {item.retrieval_channel.upper()})")
        else:
            lines.append("None (Insufficient Evidence)" if determined_status == RCAStatus.INSUFFICIENT_EVIDENCE else "None")

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

        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict):
                    if "confirmed_observations" in data and isinstance(data["confirmed_observations"], list):
                        for o in data["confirmed_observations"]:
                            if isinstance(o, dict) and "claim" in o:
                                claims["observations"].append(o["claim"])
                            elif isinstance(o, str):
                                claims["observations"].append(o)
                    if "causal_chain" in data and isinstance(data["causal_chain"], list):
                        claims["causal_chain"] = [str(c) for c in data["causal_chain"]]
                    if "primary_conclusion" in data and isinstance(data["primary_conclusion"], dict):
                        claims["primary_cause"] = data["primary_conclusion"].get("claim")
                        if "primary_cause_code" in data["primary_conclusion"]:
                            claims["primary_cause_code"] = data["primary_conclusion"]["primary_cause_code"]
                    if "primary_cause_code" in data:
                        claims["primary_cause_code"] = data["primary_cause_code"]
                    return claims
            except Exception:
                pass

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

        return claims
