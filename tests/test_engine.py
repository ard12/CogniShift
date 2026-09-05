"""Tests for the CogniShift Agentic Execution Engine (Phase 5)."""

import pytest
import os
import json
from datetime import datetime
from fastapi.testclient import TestClient

from cognishift.app.main import app
from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.engine import (
    execute_agent_run,
    resume_agent_run,
    parse_tool_call,
    is_capability_or_conversational_query,
)
from cognishift.core.retriever import retrieve_context, MAX_DISTANCE_THRESHOLD
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def set_simulated_mode(monkeypatch):
    """Ensure tests run cleanly in simulated mode without requiring active Ollama."""
    monkeypatch.setattr(settings, "operating_mode", "simulated")


@pytest.fixture(autouse=True)
async def setup_test_data():
    """Ensure workspace 1, agent 1, and industrial tools are present in test DB."""
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'MRPL Refinery', 'Main Test Unit')")
        
        tools = [
            (1, 'check_pressure', 'Check Pressure Reading', 'read_only', 0, 'check_pressure'),
            (2, 'check_temperature', 'Check Temperature Reading', 'read_only', 0, 'check_temperature'),
            (3, 'run_diagnostic', 'Run Equipment Diagnostic', 'low_risk', 0, 'run_diagnostic'),
            (4, 'emergency_pressure_relief', 'Emergency Pressure Relief', 'service_interrupting', 1, 'emergency_pressure_relief'),
            (5, 'restart_component', 'Restart System Component', 'sensitive', 1, 'restart_component'),
        ]
        for t in tools:
            await db.execute(
                "INSERT OR IGNORE INTO tool_definitions (id, name, description, risk_level, requires_approval, implementation_key) VALUES (?, ?, ?, ?, ?, ?)",
                t
            )
            
        await db.execute("""
            INSERT INTO agent_definitions 
            (id, workspace_id, name, description, system_instructions, model_name, approval_required, allowed_tool_ids)
            VALUES (1, 1, 'Maintenance Assistant', 'Assists with equipment', 'Instructions', 'llama3.2:3b', 0, '[1, 2, 3, 4, 5]')
            ON CONFLICT(id) DO UPDATE SET allowed_tool_ids = '[1, 2, 3, 4, 5]', approval_required = 0
        """)
        await db.commit()


@pytest.mark.asyncio
async def test_parse_tool_call():
    """Verify tool call extraction uses strict structured action protocol only."""
    allowed = ["check_pressure", "check_temperature", "emergency_pressure_relief"]

    # 1. Strict JSON markdown code block with canonical action protocol (P0-1 & P0-2)
    json_text = '```json\n{"action": "tool_call", "tool_name": "check_pressure", "parameters": {"sensor_id": "PT-101"}, "reason": "Nominal check"}\n```'
    is_tool, name, params, reason = parse_tool_call(json_text, allowed)
    assert is_tool is True
    assert name == "check_pressure"
    assert params == {"sensor_id": "PT-101"}
    assert reason == "Nominal check"

    # 2. Plain text pattern must NOT trigger execution (P0-1 regression guarantee)
    text = "I will check the telemetry now. TOOL: check_temperature(sensor_id=TT-204)"
    is_tool, name, params, reason = parse_tool_call(text, allowed)
    assert is_tool is False
    assert name is None

    # 3. Intent fallback from prompt must NOT trigger execution (P0-1 regression guarantee)
    prompt = "Please run check_pressure on sensor PT-400"
    is_tool, name, params, reason = parse_tool_call("Let me look at this.", allowed, user_prompt=prompt)
    assert is_tool is False
    assert name is None

    # 4. Explanatory prose: zero tool calls
    is_tool, name, params, reason = parse_tool_call("The boiler operating manual recommends checking flange seals.", allowed, user_prompt="What are seal specs?")
    assert is_tool is False
    assert name is None


@pytest.mark.asyncio
async def test_direct_answer_run():
    """Verify a general query completes directly and records timeline events."""
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="What are the basic guidelines for refinery pump maintenance?",
        user_id="test_operator"
    )

    assert run_res.status == "completed"
    assert run_res.result_text is not None
    assert run_res.workspace_id == 1
    assert run_res.agent_id == 1

    # Verify run_events were logged
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM run_events WHERE run_id = ? ORDER BY id ASC", (run_res.id,))
        events = await cursor.fetchall()
        event_types = [e["event_type"] for e in events]
        
        assert "run_started" in event_types
        assert "retrieval_started" in event_types
        assert "retrieval_completed" in event_types
        assert "model_prompt" in event_types
        assert "model_response" in event_types
        assert "completed" in event_types


@pytest.mark.asyncio
async def test_safe_tool_execution():
    """Verify safe tools (read_only) execute immediately and complete the run."""
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Please check pressure on sensor PT-101",
        user_id="test_operator"
    )

    assert run_res.status == "completed"
    assert run_res.result_text is not None

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM run_events WHERE run_id = ?", (run_res.id,))
        events = [e["event_type"] for e in await cursor.fetchall()]
        assert "tool_executing" in events
        assert "tool_executed" in events


@pytest.mark.asyncio
async def test_high_risk_tool_pauses_for_approval():
    """Verify sensitive tools trigger a status='paused' state and queue in approval_requests."""
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Critical overpressure detected! Actuate emergency pressure relief on chamber REACTOR-B immediately!",
        user_id="test_operator"
    )

    # Must pause
    assert run_res.status == "paused"
    assert "paused" in run_res.result_text.lower()

    # Must have created an approval request in DB
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM approval_requests WHERE run_id = ?", (run_res.id,))
        approval = await cursor.fetchone()
        assert approval is not None
        assert approval["status"] == "pending"
        assert approval["risk_level"] == "service_interrupting"


@pytest.mark.asyncio
async def test_resume_after_approval():
    """Verify a paused run resumes and completes after a supervisor approves it."""
    # 1. Trigger high-risk run
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Emergency vent needed: emergency_pressure_relief on chamber REACTOR-B",
        user_id="test_operator"
    )
    assert run_res.status == "paused"

    # 2. Simulate Supervisor Approval
    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM approval_requests WHERE run_id = ?", (run_res.id,))
        req = await cursor.fetchone()
        assert req is not None
        req_id = req["id"]

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "UPDATE approval_requests SET status = 'approved', reviewed_by = 'shift_supervisor', reviewed_at = ? WHERE id = ?",
            (now_str, req_id)
        )
        await db.commit()

    # 3. Resume Run
    resumed = await resume_agent_run(run_id=run_res.id)
    assert resumed.status == "completed"
    assert resumed.completed_at is not None

    # Verify event logged
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM run_events WHERE run_id = ?", (run_res.id,))
        event_types = [e["event_type"] for e in await cursor.fetchall()]
        assert "tool_executed" in event_types
        assert "completed" in event_types


@pytest.mark.asyncio
async def test_resume_after_rejection():
    """Verify a paused run terminates safely when rejected by supervisor."""
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Venting test: emergency_pressure_relief on chamber UNIT-10",
        user_id="test_operator"
    )
    assert run_res.status == "paused"

    # Supervisor rejects
    async with get_db() as db:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "UPDATE approval_requests SET status = 'rejected', reviewed_by = 'chief_engineer', reviewed_at = ? WHERE run_id = ?",
            (now_str, run_res.id)
        )
        await db.commit()

    resumed = await resume_agent_run(run_id=run_res.id)
    assert resumed.status == "completed"
    assert "rejected" in resumed.result_text.lower()


def test_runs_api_endpoints():
    """Test full HTTP REST endpoints for Runs API."""
    try:
        from tests.conftest import TEST_OPERATOR_TOKEN
    except ImportError:
        import importlib.util
        from pathlib import Path
        conftest_path = Path(__file__).parent / "conftest.py"
        spec = importlib.util.spec_from_file_location("local_conftest", conftest_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        TEST_OPERATOR_TOKEN = getattr(mod, "TEST_OPERATOR_TOKEN", "mock_token")
    client = TestClient(app)

    auth_headers = {"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"}

    # 1. Trigger a Run via POST /api/v1/runs
    post_res = client.post(
        "/api/v1/runs",
        json={
            "workspace_id": 1,
            "agent_id": 1,
            "input_text": "Verify thermocouple readings",
            "user_id": "api_tester"
        },
        headers=auth_headers
    )
    assert post_res.status_code == 200
    data = post_res.json()
    run_id = data["id"]
    assert data["status"] in ["completed", "paused"]

    # 2. List runs via GET /api/v1/runs
    list_res = client.get("/api/v1/runs?workspace_id=1", headers=auth_headers)
    assert list_res.status_code == 200
    runs = list_res.json()
    assert len(runs) >= 1
    assert any(r["id"] == run_id for r in runs)

    # 3. Get single run via GET /api/v1/runs/{id}
    get_res = client.get(f"/api/v1/runs/{run_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == run_id

    # 4. Get events timeline via GET /api/v1/runs/{id}/events
    events_res = client.get(f"/api/v1/runs/{run_id}/events", headers=auth_headers)
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 2
    assert events[0]["event_type"] == "run_started"


def test_is_capability_or_conversational_query():
    """Verify regex patterns for capability and conversational queries."""
    # True positives (should bypass domain RAG)
    assert is_capability_or_conversational_query("can you run a python script?") is True
    assert is_capability_or_conversational_query("what tools do you have?") is True
    assert is_capability_or_conversational_query("hello there") is True
    assert is_capability_or_conversational_query("who are you?") is True
    assert is_capability_or_conversational_query("what are your capabilities?") is True
    assert is_capability_or_conversational_query("can you write code") is True

    # True negatives (domain queries that require RAG)
    assert is_capability_or_conversational_query("What are the basic guidelines for refinery pump maintenance?") is False
    assert is_capability_or_conversational_query("Check vibration on pump P-101") is False
    assert is_capability_or_conversational_query("SOP for pump 610 startup sequence") is False


@pytest.mark.asyncio
async def test_capability_query_bypasses_retrieval():
    """Verify that capability queries bypass retrieval and record retrieval_bypassed event."""
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="can you run a python script?",
        user_id="test_operator"
    )
    assert run_res.status == "completed"
    assert run_res.sources_used == "None (Conversational/Capability Query)"

    async with get_db() as db:
        cursor = await db.execute("SELECT event_type FROM run_events WHERE run_id = ?", (run_res.id,))
        events = [e["event_type"] for e in await cursor.fetchall()]
        assert "retrieval_bypassed" in events
        assert "retrieval_started" not in events


@pytest.mark.asyncio
async def test_retriever_distance_threshold():
    """Verify that retriever suppresses chunks with embedding distance above threshold."""
    assert MAX_DISTANCE_THRESHOLD == 0.75
    mock_collection = MagicMock()
    mock_collection.count.return_value = 1

    # Case 1: Distance above 0.75 -> filtered out to empty string
    mock_collection.query.return_value = {
        "documents": [["Irrelevant SOP procedure chunk"]],
        "metadatas": [[{"filename": "manual.pdf", "page": 1, "source_id": 1}]],
        "distances": [[0.95]]
    }
    with patch("cognishift.core.retriever.chroma_client.get_collection", return_value=mock_collection), \
         patch("cognishift.core.retriever.embedding_model.embed", return_value=[MagicMock(tolist=lambda: [0.1] * 384)]):
        result = await retrieve_context(workspace_id=1, query="can you run python?")
        assert result == ""

    # Case 2: Distance within 0.75 -> included
    mock_collection.query.return_value = {
        "documents": [["Relevant SOP procedure chunk"]],
        "metadatas": [[{"filename": "pump_manual.pdf", "page": 4, "source_id": 1}]],
        "distances": [[0.35]]
    }
    with patch("cognishift.core.retriever.chroma_client.get_collection", return_value=mock_collection), \
         patch("cognishift.core.retriever.embedding_model.embed", return_value=[MagicMock(tolist=lambda: [0.1] * 384)]):
        result = await retrieve_context(workspace_id=1, query="pump SOP")
        assert "Relevant SOP procedure chunk" in result


@pytest.mark.asyncio
async def test_multi_turn_history_forwarded():
    """Verify that previous completed run turns are loaded into history for subsequent runs."""
    # First turn
    run1 = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Hello, my name is Operator Alex",
        user_id="test_operator"
    )
    assert run1.status == "completed"

    captured_history = []
    from cognishift.core.simulated_provider import SimulatedProvider
    original_generate = SimulatedProvider.generate_text

    async def spy_generate_text(self, prompt, system_prompt="", context="", model_name=None, history=None):
        nonlocal captured_history
        captured_history = history
        return await original_generate(self, prompt, system_prompt, context, model_name, history)

    with patch.object(SimulatedProvider, "generate_text", spy_generate_text):
        run2 = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="What did I just tell you my name was?",
            user_id="test_operator"
        )
        assert run2.status == "completed"
        assert captured_history is not None
        assert len(captured_history) >= 2
        assert any("Operator Alex" in h["content"] for h in captured_history)
