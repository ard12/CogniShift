"""Test suite for RCA Evidence Bundle and Item schemas."""
import pytest
from cognishift.core.rca.schemas import (
    EvidenceRole,
    RCAStatus,
    RCAEvidenceItem,
    RCAEvidenceBundle,
    ChannelExecutionHealth,
)


def test_rca_evidence_item_creation():
    item = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=1,
        source_id=10,
        filename="P-101A_Maintenance_SOP.pdf",
        page_number=4,
        processing_version="v2",
        retrieval_channel="text",
        evidence_role=EvidenceRole.SOP_BASELINE,
        content="Normal suction pressure operating limit is 2.5 - 3.5 bar(g). Low suction pressure alarm trips at 1.8 bar(g).",
        confidence=0.92,
        corroborated=True,
        equipment_ids=["P-101A"],
        sensor_ids=["PT-101-SUC"]
    )
    assert item.evidence_id == "E1"
    assert item.evidence_role == EvidenceRole.SOP_BASELINE
    assert item.corroborated is True
    assert "P-101A" in item.equipment_ids
    assert "PT-101-SUC" in item.sensor_ids


def test_rca_evidence_bundle_formatting_and_lookup():
    item1 = RCAEvidenceItem(
        evidence_id="E1",
        source_type="pdf",
        workspace_id=1,
        source_id=10,
        filename="P-101A_SOP.pdf",
        page_number=4,
        retrieval_channel="text",
        evidence_role=EvidenceRole.SOP_BASELINE,
        content="Suction trip limit is 1.8 bar(g).",
        confidence=0.90,
        equipment_ids=["P-101A"]
    )
    item2 = RCAEvidenceItem(
        evidence_id="E2",
        source_type="image",
        workspace_id=1,
        source_id=12,
        filename="P-101A_PID_Schematic.pdf",
        page_number=1,
        retrieval_channel="visual",
        evidence_role=EvidenceRole.P_AND_ID,
        content="P&ID shows suction strainer S-101 upstream of P-101A suction flange.",
        confidence=0.88,
        corroborated=True,
        equipment_ids=["P-101A"]
    )

    bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        required_roles=[EvidenceRole.SOP_BASELINE, EvidenceRole.VIBRATION],
        optional_roles=[EvidenceRole.P_AND_ID],
        evidence_items=[item1, item2],
        missing_required_roles=[EvidenceRole.VIBRATION],
        contradictions=[],
        source_coverage={"sop": True, "vibration": False},
        modality_coverage={"text": True, "visual": True, "topology": False, "telemetry": False},
        channel_health=ChannelExecutionHealth(
            requested_channels=["text", "visual", "topology"],
            executed_channels=["text", "visual"],
            failed_channels=[]
        )
    )

    # Test lookup
    assert bundle.get_evidence_by_id("E1") == item1
    assert bundle.get_evidence_by_id("E2") == item2
    assert bundle.get_evidence_by_id("E99") is None

    # Test formatted reasoning prompt
    prompt_text = bundle.format_for_reasoning_prompt()
    assert "[E1]" in prompt_text
    assert "[E2]" in prompt_text
    assert "P-101A_SOP.pdf (Page 4)" in prompt_text
    assert "P-101A_PID_Schematic.pdf (Page 1) [CORROBORATED]" in prompt_text
    assert "Missing: VIBRATION" in prompt_text


def test_empty_evidence_bundle_formatting():
    bundle = RCAEvidenceBundle(
        asset_ids=["K-999"],
        evidence_items=[],
        channel_health=ChannelExecutionHealth()
    )
    prompt_text = bundle.format_for_reasoning_prompt()
    assert "No verified documentary or physical telemetry evidence retrieved" in prompt_text
