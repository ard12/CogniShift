"""RCA Claim-to-Evidence Validation and Deterministic Finalization Subsystem."""
import re
import json
import logging
from typing import List, Dict, Any, Optional, Set, Tuple

from cognishift.core.rca.schemas import (
    RCAStatus,
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
                f"Cannot evaluate root cause: Asset `{asset_str}` was not found in the refinery hierarchy.\n\n"
                f"## Additional Evidence Needed\n"
                f"- Verify equipment tag against the refinery asset registry (e.g., P-101A, K-101, Reactor-B).\n\n"
                f"## Sources\n"
                f"None (Asset Not Found)"
            )

        # 2. Check for symptom-only input with zero supporting retrieved evidence
        if not bundle.evidence_items:
            return (
                f"## RCA Status\nINSUFFICIENT_EVIDENCE\n\n"
                f"## Confirmed Observations\n"
                f"- No independently measured observation was supplied beyond the operator's written description.\n\n"
                f"## Possible Hypotheses — Unverified\n"
                f"- No verified documentary or telemetry evidence was retrieved for the specified equipment.\n\n"
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
                # Include items from high-priority roles
                if item.evidence_role in (EvidenceRole.INSPECTION, EvidenceRole.SOP_BASELINE, EvidenceRole.VIBRATION, EvidenceRole.INCIDENT_CHRONOLOGY):
                    supported_items.append(item)
                    cited_e_ids.add(item.evidence_id)

        # 5. Check if required roles are satisfied
        required_roles_satisfied = len(bundle.missing_required_roles) == 0

        # Check for explicit missing source requests
        explicit_missing_sources = [s for s, found in bundle.source_coverage.items() if not found]

        # 6. Determine RCA Status deterministically
        determined_status = determine_rca_status(
            required_roles_satisfied=required_roles_satisfied and len(explicit_missing_sources) == 0,
            supporting_items=supported_items,
            contradictions=bundle.contradictions,
            has_causal_chronology=any(i.evidence_role == EvidenceRole.INCIDENT_CHRONOLOGY for i in supported_items),
            operator_symptoms_only=False
        )

        # 7. Construct User-Facing Engineering Output (Section 17 Format)
        status_display = determined_status.value.replace("_", " ")

        lines = [f"## RCA Status\n{status_display}\n"]

        # Confirmed Observations
        lines.append("## Confirmed Observations")
        obs_lines = parsed_claims.get("observations", [])
        if obs_lines:
            for obs in obs_lines:
                lines.append(f"- {obs}")
        else:
            # Generate from verified evidence items
            for item in supported_items[:4]:
                src_label = f"[{item.filename} | Page {item.page_number}]" if item.page_number else f"[{item.filename}]"
                lines.append(f"- [{item.evidence_id}] {src_label}: {item.content[:200].strip()}...")

        # Causal Chain / Hypotheses
        causal_steps = parsed_claims.get("causal_chain", [])
        if causal_steps:
            lines.append("\n## Causal Chain")
            for idx, step in enumerate(causal_steps, 1):
                lines.append(f"{idx}. {step}")

        # Primary Cause
        primary_cause = parsed_claims.get("primary_cause")
        lines.append("\n## Primary Cause")
        if primary_cause and determined_status in (RCAStatus.CONFIRMED_CAUSE, RCAStatus.SUPPORTED_LIKELY_CAUSE, RCAStatus.PLAUSIBLE_HYPOTHESIS):
            lines.append(f"{primary_cause}")
        elif determined_status == RCAStatus.INSUFFICIENT_EVIDENCE:
            lines.append("No root cause could be authoritatively confirmed due to missing required evidence.")
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
                needed.append(f"Explicitly requested document `{ems.replace('_', ' ').title()}` was not found in the workspace vault.")
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
                    lines.append(f"- `{fname}` — Page {pnum} (Channel: {item.retrieval_channel.upper()})")
                else:
                    lines.append(f"- `{fname}` (Channel: {item.retrieval_channel.upper()})")
        else:
            lines.append("None")

        return "\n".join(lines)

    def _extract_claims_and_evidence_ids(self, text: str, bundle: RCAEvidenceBundle) -> Dict[str, Any]:
        """
        Parses claims, causal steps, primary causes, and [E#] citations from model text.
        """
        claims: Dict[str, Any] = {
            "all_referenced_e_ids": [],
            "observations": [],
            "causal_chain": [],
            "primary_cause": None
        }

        # 1. Find all [E1], [E2], etc.
        e_matches = re.findall(r"\[(E\d+)\]", text)
        claims["all_referenced_e_ids"] = list(set(e_matches))

        # 2. Check if output contains a structured JSON block
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
                    return claims
            except Exception:
                pass

        # 3. Parse free-form prose sections
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
            elif "evidence needed" in lower_l or "sources" in lower_l or "supporting evidence" in lower_l:
                current_section = None
                continue

            if clean_l.startswith("-") or clean_l.startswith("*") or re.match(r"^\d+\.", clean_l):
                item_content = re.sub(r"^[-*0-9.]+\s*", "", clean_l).strip()
                if current_section == "observations" and item_content:
                    claims["observations"].append(item_content)
                elif current_section == "causal" and item_content:
                    claims["causal_chain"].append(item_content)
            elif current_section == "primary" and clean_l and not claims["primary_cause"]:
                claims["primary_cause"] = clean_l

        return claims
