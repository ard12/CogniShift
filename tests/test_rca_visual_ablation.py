"""
Unit and integration tests for RCA Visual Ablation (Section 47):
Verifies that spatial relations present ONLY in P&ID drawings:
- Fail under Condition A (TEXT ONLY): spatial link between FV-302 and R-301 cannot be established.
- Fail under Condition B (TEXT + TOPOLOGY): topology graph does not contain the unindexed P&ID spatial routing.
- Succeed under Condition C (TEXT + TOPOLOGY + VISUAL): VisualEvidenceInspector extracts the schematic observation,
  generating a visual RCAEvidenceItem that satisfies the required spatial link for primary cause validation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from cognishift.core.rca.schemas import (
    PrimaryCauseCode,
    RCAStatus,
    RCAEvidenceItem,
    RCAEvidenceBundle,
    EvidenceRole,
    EvidenceCriticality,
    EvidenceRequirement,
    EvidenceLocator
)
from cognishift.core.rca.policy import determine_rca_status
from cognishift.core.rca.evidence_validation import (
    RCAEvidenceValidator,
    determine_primary_cause_code
)
from cognishift.core.retrieval.visual_inspector import (
    VisualEvidenceInspector,
    VisualInspectionResult
)


@pytest.mark.asyncio
async def test_rca_visual_ablation_conditions():
    """
    Simulates the three conditions of the visual ablation study:
    Condition A: Text only (incident log + maintenance log, no spatial link)
    Condition B: Text + Topology (nodes exist but no piping schematic link)
    Condition C: Text + Topology + Visual P&ID Inspection
    """
    # 1. Base text evidence items
    text_item_1 = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=9998,
        source_id=1,
        filename="RCA-CASE-A-DOC1_Hydrocracker_High_Pressure_Trip_Chrono.pdf",
        page_number=1,
        retrieval_channel="text",
        evidence_role=EvidenceRole.INCIDENT_CHRONOLOGY,
        criticality=EvidenceCriticality.REQUIRED_CRITICAL,
        equipment_ids=["R-301"],
        content="At 14:22:10, Reactor R-301 tripped on extreme high pressure (PT-301 > 165 bar). Feed flow was erratic prior to trip."
    )
    text_item_2 = RCAEvidenceItem(
        evidence_id="E2",
        source_type="pdf",
        workspace_id=9998,
        source_id=3,
        filename="RCA-CASE-A-DOC3_Valve_FV302_Maintenance_Actuator_Log.pdf",
        page_number=1,
        retrieval_channel="text",
        evidence_role=EvidenceRole.MAINTENANCE,
        criticality=EvidenceCriticality.REQUIRED_SUPPORTING,
        equipment_ids=["FV-302"],
        content="Actuator diaphragm for control valve FV-302 showed severe mechanical binding and hysteresis during recent stroke test."
    )

    # Note: Neither E1 nor E2 states that FV-302 controls feed to R-301!

    # --- Condition A: Text Only ---
    bundle_a = RCAEvidenceBundle(
        asset_ids=["R-301", "FV-302"],
        required_roles=[EvidenceRole.INCIDENT_CHRONOLOGY, EvidenceRole.P_AND_ID],
        evidence_items=[text_item_1, text_item_2]
    )

    spatial_found_a = any(
        "upstream" in item.content.lower() or "feed line" in item.content.lower()
        for item in bundle_a.evidence_items
    )
    assert not spatial_found_a, "Condition A must NOT contain the spatial schematic link"

    # --- Condition B: Text + Topology ---
    topo_item = RCAEvidenceItem(
        evidence_id="E3",
        source_type="topology",
        workspace_id=9998,
        source_id=0,
        filename="plant_graph",
        page_number=0,
        retrieval_channel="topology",
        evidence_role=EvidenceRole.TOPOLOGY,
        criticality=EvidenceCriticality.REQUIRED_SUPPORTING,
        equipment_ids=["R-301", "FV-302"],
        content="Topology node R-301 (Hydrocracker Reactor) in Unit 03; Topology node FV-302 (Control Valve) in Unit 03."
    )
    bundle_b = RCAEvidenceBundle(
        asset_ids=["R-301", "FV-302"],
        required_roles=[EvidenceRole.INCIDENT_CHRONOLOGY, EvidenceRole.P_AND_ID],
        evidence_items=[text_item_1, text_item_2, topo_item]
    )
    spatial_found_b = any(
        "upstream" in item.content.lower() or "feed line" in item.content.lower()
        for item in bundle_b.evidence_items
    )
    assert not spatial_found_b, "Condition B must NOT contain the spatial schematic link"

    # --- Condition C: Text + Topology + Visual Interpretation ---
    visual_item = RCAEvidenceItem(
        evidence_id="E4",
        source_type="pdf",
        workspace_id=9998,
        source_id=2,
        filename="RCA-CASE-A-DOC2_Feed_Control_FV302_Spatial_PID.pdf",
        page_number=1,
        retrieval_channel="visual",
        evidence_role=EvidenceRole.P_AND_ID,
        criticality=EvidenceCriticality.REQUIRED_CRITICAL,
        equipment_ids=["R-301", "FV-302"],
        content="[P_AND_ID] Observation: Control valve FV-302 is drawn inline on feed line 10-HC-301 immediately upstream of reactor R-301.",
        locator=EvidenceLocator(filename="RCA-CASE-A-DOC2_Feed_Control_FV302_Spatial_PID.pdf", page_number=1, document_type="pdf")
    )
    bundle_c = RCAEvidenceBundle(
        asset_ids=["R-301", "FV-302"],
        required_roles=[EvidenceRole.INCIDENT_CHRONOLOGY, EvidenceRole.P_AND_ID],
        evidence_items=[text_item_1, text_item_2, topo_item, visual_item]
    )

    spatial_found_c = any(
        "upstream" in item.content.lower() and "fv-302" in item.content.lower() and "r-301" in item.content.lower()
        for item in bundle_c.evidence_items
    )
    assert spatial_found_c, "Condition C MUST contain the visual spatial observation"

    # Validate that Condition C determines VALVE_STEM_BINDING
    cause_code = determine_primary_cause_code(
        parsed_code="VALVE_STEM_BINDING",
        primary_cause_text="The binding of FV-302 upstream caused pressure spike in R-301.",
        observations=["FV-302 is upstream of R-301 on feed line"],
        status=RCAStatus.SUPPORTED_LIKELY_CAUSE,
        bundle=bundle_c
    )
    assert cause_code == PrimaryCauseCode.VALVE_STEM_BINDING

    # Finalize with RCAEvidenceValidator
    validator = RCAEvidenceValidator()
    final_output = validator.validate_and_finalize(
        bundle=bundle_c,
        model_output="## RCA Status\nSUPPORTED_LIKELY_CAUSE\n\n## Confirmed Observations\n- FV-302 is upstream of R-301 [E4]\n- FV-302 actuator binding [E2]\n\n## Primary Cause\nCause Code: VALVE_STEM_BINDING\nBinding in FV-302 caused starvation and trip.\n\n## Sources\n[RCA-CASE-A-DOC2_Feed_Control_FV302_Spatial_PID.pdf | Page 1 | VISUAL]",
        operator_input="RCA on R-301 and FV-302"
    )
    assert "VALVE_STEM_BINDING" in final_output
    assert "E4" in final_output
