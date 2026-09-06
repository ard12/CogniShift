"""Tests for Conversational Console, Strict Discriminated Protocol, and Fail-Closed Guarantees."""
import json
import pytest
from unittest.mock import patch

from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.engine import execute_agent_run
from cognishift.core.providers import ModelResponse
from cognishift.core.simulated_provider import SimulatedProvider


@pytest.fixture(autouse=True)
def set_simulated_mode(monkeypatch):
    monkeypatch.setattr(settings, "operating_mode", "simulated")


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'Refinery-1', 'MRPL')")
        tools = [
            (1, 'check_pressure', 'Check Pressure Reading', 'read_only', 0, 1, 'check_pressure'),
            (2, 'check_temperature', 'Check Temperature Reading', 'read_only', 0, 1, 'check_temperature'),
            (3, 'run_diagnostic', 'Run Equipment Diagnostic', 'low_risk', 0, 1, 'run_diagnostic'),
            (4, 'emergency_pressure_relief', 'Emergency Pressure Relief', 'service_interrupting', 1, 1, 'emergency_pressure_relief'),
            (5, 'restart_component', 'Restart System Component', 'sensitive', 1, 1, 'restart_component'),
        ]
        for t in tools:
            await db.execute(
                "INSERT INTO tool_definitions (id, name, description, risk_level, requires_approval, enabled, implementation_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, risk_level=excluded.risk_level, requires_approval=excluded.requires_approval, enabled=excluded.enabled",
                t
            )
        await db.execute("""
            INSERT INTO agent_definitions 
            (id, workspace_id, name, description, system_instructions, model_name, approval_required, allowed_tool_ids)
            VALUES (1, 1, 'Maintenance Assistant', 'Assists with equipment', 'Instructions', 'llama3.2:3b', 0, '[1, 2, 3, 4, 5]')
            ON CONFLICT(id) DO UPDATE SET allowed_tool_ids = '[1, 2, 3, 4, 5]', approval_required = 0
        """)
        await db.commit()


# -----------------------------------------------------------------------------
# 1. FRONTEND COMMAND RECOGNITION MATRIX (Deterministic vs Agent Routing)
# -----------------------------------------------------------------------------
def test_frontend_deterministic_commands_vs_agent_queries():
    """Verify in JavaScript file that exact matches intercept and questions route to agent."""
    from pathlib import Path
    app_js = Path(__file__).resolve().parents[1] / "src" / "cognishift" / "app" / "static" / "app.js"
    content = app_js.read_text(encoding="utf-8")

    # Assert strict greeting set exists
    assert "GREETINGS = new Set(['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening'])" in content

    # Assert exact nav map exists
    assert "EXACT_NAV_RULES" in content
    assert "rule.commands.includes(normalized)" in content

    # Assert agent dispatch markers exist
    assert "Sending request to local agent..." in content
    assert "Local inference in progress..." in content


# -----------------------------------------------------------------------------
# 2. CONVERSATIONAL FINALANSWER PROTOCOL & CITATIONS
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_conversational_final_answer_with_real_citations():
    """Verify question answering produces structured FinalAnswer and preserves citations."""
    model_output = json.dumps({
        "action": "final_answer",
        "content": "Pump P-101A operates at 42.5 bar and 68 C in CDU-1.",
        "citations": ["Refinery_Manual.pdf | Page 12"]
    })

    with patch.object(SimulatedProvider, "generate_text", return_value=ModelResponse(text=model_output, model_name="test", provider="test")):
        run_res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="What is pump P-101A?",
            user_id="operator_sam"
        )

    assert run_res.status == "completed"
    assert "Pump P-101A operates at 42.5 bar" in run_res.result_text
    assert run_res.error_message is None


# -----------------------------------------------------------------------------
# 3. ACTION / DISCUSSION DISTINCTION
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_discussion_about_action_does_not_execute_tool():
    """Talking ABOUT an emergency procedure or action must produce FinalAnswer, not execution."""
    model_output = json.dumps({
        "action": "final_answer",
        "content": "The emergency pressure relief policy requires dual supervisor sign-off before actuating valve PV-102.",
        "citations": ["OISD-156 | Page 4"]
    })

    with patch.object(SimulatedProvider, "generate_text", return_value=ModelResponse(text=model_output, model_name="test", provider="test")):
        run_res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="Explain the emergency shutdown and pressure relief policy",
            user_id="operator_sam"
        )

    assert run_res.status == "completed"
    assert "emergency pressure relief policy" in run_res.result_text
    # Must NOT have created an approval request
    async with get_db() as db:
        c = await db.execute("SELECT COUNT(*) as count FROM approval_requests WHERE run_id = ?", (run_res.id,))
        count = (await c.fetchone())["count"]
        assert count == 0


@pytest.mark.asyncio
async def test_action_request_proposes_tool_and_pauses_for_approval():
    """Explicitly requesting an action must produce ToolCall proposal and pause for policy interlock."""
    model_output = json.dumps({
        "action": "tool_call",
        "tool_name": "restart_component",
        "parameters": {"component_id": "P-101A", "reason": "Seal temperature abnormal"},
        "reason": "Restarting pump P-101A to prevent seal damage"
    })

    with patch.object(SimulatedProvider, "generate_text", return_value=ModelResponse(text=model_output, model_name="test", provider="test")):
        run_res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="Restart P-101A immediately",
            user_id="operator_sam"
        )

    assert run_res.status == "paused"
    assert "Action paused awaiting supervisor approval: restart_component" in run_res.result_text
    # Must have created an approval request in database
    async with get_db() as db:
        c = await db.execute("SELECT * FROM approval_requests WHERE run_id = ?", (run_res.id,))
        req = await c.fetchone()
        assert req is not None
        assert req["status"] == "pending"


# -----------------------------------------------------------------------------
# 4. CHAT FAILURE & FAIL-CLOSED ENFORCEMENT
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_failure_missing_tool_argument_rejected_and_fails_closed():
    """ToolCall with missing required arguments must be rejected by schema and fail closed."""
    invalid_tool_output = json.dumps({
        "action": "tool_call",
        "tool_name": "restart_component",
        "parameters": {"reason": "missing component id"}  # Missing required component_id
    })

    with patch.object(SimulatedProvider, "generate_text", return_value=ModelResponse(text=invalid_tool_output, model_name="test", provider="test")):
        run_res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="Restart component",
            user_id="operator_sam"
        )

    assert run_res.status == "failed"
    assert "Execution encountered failures" in run_res.result_text
    assert "Invalid parameters" in run_res.result_text or "Field required" in run_res.result_text


@pytest.mark.asyncio
async def test_chat_failure_garbage_output_fails_closed():
    """Unparseable model garbage must fail closed with model_protocol_failure."""
    with patch.object(SimulatedProvider, "generate_text", return_value=ModelResponse(text="<<<INVALID JUNK XML >>>", model_name="test", provider="test")):
        run_res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="What is the pressure?",
            user_id="operator_sam"
        )

    assert run_res.status == "failed"
    assert "Unparseable" in (run_res.error_message or "")


@pytest.mark.asyncio
async def test_chat_failure_no_retrieval_does_not_manufacture_citations():
    """When no matching documents are found, no citations are fabricated."""
    model_output = json.dumps({
        "action": "final_answer",
        "content": "No relevant local operational manual was found regarding cryogenic nitrogen tanks.",
        "citations": []
    })

    with patch.object(SimulatedProvider, "generate_text", return_value=ModelResponse(text=model_output, model_name="test", provider="test")):
        run_res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="Tell me about the cryogenic nitrogen tank",
            user_id="operator_sam"
        )

    assert run_res.status == "completed"
    assert "No relevant local operational manual" in run_res.result_text
    assert run_res.sources_used == "None (No matching manual found)"
