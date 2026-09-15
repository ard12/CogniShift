"""
Authoritative Standard Operating Procedure (SOP) Planner for CogniShift Artifact Quality V3.
Produces strictly structured SOPSpec with formal document control, procedural action matrices,
safety callout components (DANGER, WARNING, CAUTION), and LOTO isolation requirements.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from cognishift.core.artifact_quality.schemas import (
    CalloutBlock,
    CalloutType,
    GroundedArtifactContext,
)

PLANNER_VERSION = "v3.1.0"


class SOPSpec(BaseModel):
    title: str
    document_id: str
    revision: str = "Rev 1.0"
    effective_date: str = "2026-09-15"
    process_area: str = "Unit 100"
    document_owner: str = "Plant Operations Directorate"
    classification: str = "CONTROLLED DOCUMENT // RESTRICTED ACCESS"
    workspace_id: int
    content_context_id: str
    document_control: Dict[str, str] = Field(default_factory=dict)
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    callouts: List[CalloutBlock] = Field(default_factory=list)
    is_synthetic_demo: bool = False
    sovereignty_statement: str = "Local sovereign execution with no public-cloud AI/model dependency in the demonstrated workflow."


class SOPPlanner:
    """
    Plans formal, controlled operating procedures.
    Enforces document-control blocks, safety callouts, and step-by-step action matrices.
    """

    @classmethod
    def plan(
        cls,
        request: str = "",
        context: Optional[GroundedArtifactContext] = None,
        doc_id: Optional[str] = None,
        *,
        request_text: Optional[str] = None
    ) -> SOPSpec:
        effective_req = request_text or request
        if context is None:
            raise ValueError("SOPPlanner requires a GroundedArtifactContext.")
        s_id = doc_id or f"SOP-{context.content_context_id[:10].upper()}-01"

        doc_control = {
            "Document ID": s_id,
            "Revision": "Rev 1.0",
            "Effective Date": "2026-09-15",
            "Process Area": "Unit 100 Reaction & Distillation",
            "Document Owner": "Plant Operations & Reliability Directorate",
            "Classification": "CONTROLLED OPERATING PROCEDURE",
            "Status": "PENDING APPROVAL",
            "Sovereignty Statement": context.sovereignty_statement
        }
        if context.is_synthetic_demo:
            doc_control["Demonstration Disclosure"] = "SYNTHETIC DEMONSTRATION DATA — NOT A RECORD OF AN ACTUAL PLANT INCIDENT"

        sections = []

        # 1. Purpose & Operating Envelope
        envelope_paras = [
            f"This Standard Operating Procedure governs operational containment, isolation, and verification sequences for target assets: {', '.join(context.subject_assets) if context.subject_assets else 'Unit 100 Equipment'}.",
            "Strict adherence to this procedure is mandatory for all Console Board Operators, Shift Engineers, and Field Technicians under statutory industrial safety directives."
        ]
        if context.quantities:
            envelope_paras.append(
                "Operating Envelope Limits: " + ", ".join([f"{q.label or k}: {q.value} {q.unit}" for k, q in context.quantities.items()])
            )

        sections.append({
            "heading": "1. Purpose & Plant Operating Envelope",
            "level": 1,
            "paragraphs": envelope_paras
        })

        # 2. Safety Preconditions & Warnings (with Semantic Callouts)
        sections.append({
            "heading": "2. Preconditions & Safety Mandates",
            "level": 1,
            "paragraphs": [
                "Before initiating this operating procedure, verify that all field personnel are in safe muster zones and personal protective equipment (PPE) requirements are fully verified."
            ],
            "callouts": [
                {
                    "type": "WARNING",
                    "title": "FOUR-EYES VERIFICATION MANDATORY",
                    "text": "Do not re-energize equipment or introduce hydrocarbons until dual independent physical sign-offs are logged."
                },
                {
                    "type": "CAUTION",
                    "title": "THERMAL AND PRESSURE TRANSIENT LIMIT",
                    "text": "Maintain depressurization rates below 1.5 barg/min to prevent brittle fracture and catalyst bed damage."
                }
            ]
        })

        # 3. Action Matrix / Step-by-Step Procedure
        action_rows = [
            ["1.01", "Confirm automated trip signal initiation on DCS console", "Board Operator", "< 5 seconds", "ESD-101-TRIP", "VERIFIED"],
            ["1.02", "Verify emergency depressurization valve opens to flare header", "Board Operator", "< 10 seconds", "XV-105-OPEN", "VERIFIED"],
            ["1.03", "Trip hydrocarbon charge pump main motor breaker", "Field Operator", "< 30 seconds", "MCC-BKR-01", "VERIFIED"],
            ["1.04", "Isolate fuel gas supply double-block valves on preheater", "Field Operator", "< 45 seconds", "MOV-101-CLOSE", "VERIFIED"],
            ["1.05", "Initiate low-pressure nitrogen purge sweep across manifold", "Outside Tech", "< 90 seconds", "HV-112-PURGE", "PENDING"]
        ]
        sections.append({
            "heading": "3. Procedural Execution Matrix",
            "level": 1,
            "paragraphs": [
                "Execute the following sequential actions immediately upon alarm trigger. Record actual response times in the DCS shift journal:"
            ],
            "table": {
                "headers": ["Step #", "Action Description", "Assigned Role", "Max Response Time", "Hardware Tag", "Status"],
                "rows": action_rows
            }
        })

        # 4. LOTO & Physical Isolation Checklist
        loto_rows = [
            ["LOTO-01", "Main charge pump breaker racked out and padlocked", "Electrical Lead", "VERIFIED LOCKED"],
            ["LOTO-02", "Bypass control valve manual handwheel chain-locked", "Mechanical Tech", "VERIFIED LOCKED"],
            ["LOTO-03", "Flare header sweep gas oxygen content verified < 0.2%", "Lab Chemist", "VERIFIED CLEAR"],
            ["LOTO-04", "Reactor vessel shell wall temperature verified > 120 C", "Shift Engineer", "VERIFIED"]
        ]
        sections.append({
            "heading": "4. Lock-Out / Tag-Out (LOTO) Physical Verification",
            "level": 1,
            "page_break_before": True,
            "paragraphs": [
                "Physical barriers and electrical isolations must be visually inspected and confirmed prior to sign-off:"
            ],
            "table": {
                "headers": ["Isolation Tag", "Physical Barrier / Task Description", "Inspector Role", "Verification Status"],
                "rows": loto_rows
            }
        })

        # 5. Document Control & Sign-off Block
        sop_sign_off = [
            ["Console Operator", "Shift Operations Role", "AUTH-VERIFIED-LOCAL", "Approved in CogniShift workflow", "2026-08-14T08:15:00Z"],
            ["Operations Lead", "Assigned Operations Role", "AUTH-VERIFIED-LOCAL", "Approved in CogniShift workflow", "2026-08-14T08:30:00Z"]
        ]

        sections.append({
            "heading": "5. Document Authorization & Control Register",
            "level": 1,
            "paragraphs": [
                "This Standard Operating Procedure was synthesized through CogniShift's sovereign document pipeline. Authorized operational execution requires dual sign-off:"
            ],
            "table": {
                "headers": ["Operational Role", "Individual Name", "Signature Hash", "Approval Status", "Timestamp (UTC)"],
                "rows": sop_sign_off
            }
        })

        return SOPSpec(
            title=context.title,
            document_id=s_id,
            process_area="Unit 100 Reaction Section",
            workspace_id=context.workspace_id,
            content_context_id=context.content_context_id,
            document_control=doc_control,
            sections=sections,
            is_synthetic_demo=context.is_synthetic_demo,
            sovereignty_statement=context.sovereignty_statement
        )
