"""End-to-End RCA Runtime Integration Test Suite for CogniShift."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from cognishift.app.db.database import init_db, get_db
from cognishift.core.engine import execute_agent_run
from cognishift.core.semantic_router import SemanticIntent, SemanticRoutingResult
from cognishift.core.providers import ModelResponse
from cognishift.core.rca.schemas import (
    EvidenceRole,
    RCAStatus,
    RCAEvidenceItem,
    RCAEvidenceBundle,
    ChannelExecutionHealth,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()


@pytest.mark.asyncio
async def test_rca_runtime_preserves_grounded_root_cause():
    ws_id = 901
    ag_id = 901

    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (?, 'RCA Test Refinery', 'Test')",
            (ws_id,)
        )
        await db.execute(
            """INSERT OR IGNORE INTO agent_definitions
               (id, workspace_id, name, description, model_name, system_instructions)
               VALUES (?, ?, 'Lead RCA Engineer', 'Lead engineer', 'qwen2.5:7b', 'Perform rigorous RCA.')""",
            (ag_id, ws_id)
        )
        await db.execute(
            """INSERT OR IGNORE INTO knowledge_sources
               (id, workspace_id, name, original_filename, source_type, active_processing_version, processing_status)
               VALUES (9001, ?, 'P-101A_Inspection.pdf', 'P-101A_Inspection.pdf', 'pdf', 'v1', 'completed')""",
            (ws_id,)
        )
        await db.execute(
            """INSERT OR IGNORE INTO knowledge_sources
               (id, workspace_id, name, original_filename, source_type, active_processing_version, processing_status)
               VALUES (9002, ?, 'P-101A_SOP.pdf', 'P-101A_SOP.pdf', 'pdf', 'v1', 'completed')""",
            (ws_id,)
        )
        await db.commit()

    mock_bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        required_roles=[EvidenceRole.INSPECTION, EvidenceRole.SOP_BASELINE],
        evidence_items=[
            RCAEvidenceItem(
                evidence_id="E1",
                source_type="pdf",
                workspace_id=ws_id,
                source_id=9001,
                filename="P-101A_Inspection.pdf",
                page_number=3,
                retrieval_channel="text",
                evidence_role=EvidenceRole.INSPECTION,
                content="Strainer S-101 was 80% choked by particulate debris, dropping pump suction head.",
                confidence=0.95,
                equipment_ids=["P-101A"]
            ),
            RCAEvidenceItem(
                evidence_id="E2",
                source_type="pdf",
                workspace_id=ws_id,
                source_id=9002,
                filename="P-101A_SOP.pdf",
                page_number=4,
                retrieval_channel="text",
                evidence_role=EvidenceRole.SOP_BASELINE,
                content="Low suction pressure trip activates at 1.8 bar(g) to prevent severe cavitation damage.",
                confidence=0.92,
                equipment_ids=["P-101A"]
            )
        ],
        missing_required_roles=[],
        source_coverage={"inspection_report": True, "maintenance_sop": True},
        channel_health=ChannelExecutionHealth(
            requested_channels=["text", "visual", "topology"],
            executed_channels=["text", "visual", "topology"]
        )
    )

    # Mock provider returning synthesis referencing E1 and E2
    mock_llm_response = ModelResponse(
        text="""```json
{
  "thought": "Synthesizing root cause from verified inspection findings and baseline operating limits.",
  "action": "final_answer",
  "content": "## Confirmed Observations\\n- [E1] Strainer S-101 was 80% choked by particulate debris.\\n- [E2] Low suction pressure trip triggered below 1.8 bar(g).\\n\\n## Primary Cause\\nChoked suction strainer S-101 starved the pump, inducing severe cavitation and triggering low-suction trip.",
  "citations": ["P-101A_Inspection.pdf | Page 3", "P-101A_SOP.pdf | Page 4"]
}
```""",
        model_name="qwen2.5:7b",
        provider="ollama",
        success=True
    )

    with patch("cognishift.core.rca.evidence_acquisition.RCAEvidenceAcquirer.acquire_evidence", new=AsyncMock(return_value=mock_bundle)), \
         patch("cognishift.core.engine.get_provider") as mock_gp:

        mock_provider = AsyncMock()
        mock_provider.generate_text.return_value = mock_llm_response
        mock_provider.get_model_info = MagicMock(return_value={"status": "available"})
        mock_gp.return_value = mock_provider

        run_resp = await execute_agent_run(
            workspace_id=ws_id,
            agent_id=ag_id,
            input_text="Why did pump P-101A trip? Check the inspection report and maintenance SOP."
        )

        assert run_resp.status == "completed"
        # Verify destructive finalizer was NOT used
        assert "No root cause is confirmed from the symptom-only information provided" not in run_resp.result_text
        assert "## RCA Status" in run_resp.result_text
        assert "CONFIRMED CAUSE" in run_resp.result_text or "SUPPORTED LIKELY CAUSE" in run_resp.result_text
        assert "## Primary Cause" in run_resp.result_text
        assert "Choked suction strainer S-101" in run_resp.result_text
        assert "## Sources" in run_resp.result_text
        assert "P-101A_Inspection.pdf" in run_resp.result_text


@pytest.mark.asyncio
async def test_rca_runtime_ood_asset_fail_closed():
    ws_id = 902
    ag_id = 902

    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, 'RCA OOD WS')", (ws_id,))
        await db.execute(
            "INSERT OR IGNORE INTO agent_definitions (id, workspace_id, name, model_name) VALUES (?, ?, 'Eng', 'qwen2.5:7b')",
            (ag_id, ws_id)
        )
        await db.commit()

    run_resp = await execute_agent_run(
        workspace_id=ws_id,
        agent_id=ag_id,
        input_text="Why did compressor K-888 trip?"
    )

    assert run_resp.status == "completed"
    assert "ASSET_NOT_FOUND" in run_resp.result_text
    assert "Equipment `K-888` is not registered" in run_resp.result_text
    assert "None (Asset Not Found)" in (run_resp.sources_used or "")


@pytest.mark.asyncio
async def test_rca_runtime_final_step_tool_lockout():
    ws_id = 903
    ag_id = 903

    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, 'RCA Tool Lockout WS')", (ws_id,))
        await db.execute(
            "INSERT OR IGNORE INTO agent_definitions (id, workspace_id, name, model_name) VALUES (?, ?, 'Eng', 'qwen2.5:7b')",
            (ag_id, ws_id)
        )
        await db.commit()

    mock_bundle = RCAEvidenceBundle(
        asset_ids=["P-101A"],
        evidence_items=[
            RCAEvidenceItem(
                evidence_id="E1",
                source_type="pdf",
                workspace_id=ws_id,
                filename="P-101A_SOP.pdf",
                page_number=1,
                retrieval_channel="text",
                evidence_role=EvidenceRole.SOP_BASELINE,
                content="Standard pump operation guidelines.",
                confidence=0.90
            )
        ],
        channel_health=ChannelExecutionHealth(executed_channels=["text"])
    )

    # Step responses: on final step, model illegally attempts a tool call proposal
    illegal_tool_response = ModelResponse(
        text='{"action": "tool_call", "tool_name": "check_temperature", "parameters": {"sensor_id": "TT-101"}, "reason": "Checking bearing temp before answering"}',
        model_name="qwen2.5:7b",
        provider="ollama",
        success=True
    )

    with patch("cognishift.core.rca.evidence_acquisition.RCAEvidenceAcquirer.acquire_evidence", new=AsyncMock(return_value=mock_bundle)), \
         patch("cognishift.core.engine.get_provider") as mock_gp:

        mock_provider = AsyncMock()
        mock_provider.generate_text.return_value = illegal_tool_response
        mock_provider.get_model_info = MagicMock(return_value={"status": "available"})
        mock_gp.return_value = mock_provider

        run_resp = await execute_agent_run(
            workspace_id=ws_id,
            agent_id=ag_id,
            input_text="Investigate P-101A trip and explain the cause."
        )

        # The run completes cleanly because tool call proposal was intercepted on final step and converted
        assert run_resp.status == "completed"
        assert run_resp.error_message is None
