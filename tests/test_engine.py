"""Tests for the CogniShift Agentic Execution Engine (Phase 5)."""

import pytest
import os
import json
from datetime import datetime
from fastapi.testclient import TestClient

from cognishift.app.main import app
from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.engine import execute_agent_run, resume_agent_run, parse_tool_call


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
    """Verify tool call extraction from JSON blocks and plain text patterns."""
    allowed = ["check_pressure", "check_temperature", "emergency_pressure_relief"]

    # 1. JSON markdown code block
    json_text = '```json\n{"tool": "check_pressure", "parameters": {"sensor_id": "PT-101"}, "reason": "Nominal check"}\n```'
    is_tool, name, params, reason = parse_tool_call(json_text, allowed)
    assert is_tool is True
    assert name == "check_pressure"
    assert params == {"sensor_id": "PT-101"}
    assert reason == "Nominal check"

    # 2. Plain text pattern
    text = "I will check the telemetry now. TOOL: check_temperature(sensor_id=TT-204)"
    is_tool, name, params, reason = parse_tool_call(text, allowed)
    assert is_tool is True
    assert name == "check_temperature"
    assert params.get("sensor_id") == "TT-204"

    # 3. Intent fallback from prompt
    prompt = "Please run check_pressure on sensor PT-400"
    is_tool, name, params, reason = parse_tool_call("Let me look at this.", allowed, user_prompt=prompt)
    assert is_tool is True
    assert name == "check_pressure"
    assert params.get("sensor_id") == "PT-400"

    # 4. No tool needed
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
    client = TestClient(app)

    # 1. Trigger a Run via POST /api/v1/runs
    post_res = client.post(
        "/api/v1/runs",
        json={
            "workspace_id": 1,
            "agent_id": 1,
            "input_text": "Verify thermocouple readings",
            "user_id": "api_tester"
        }
    )
    assert post_res.status_code == 200
    data = post_res.json()
    run_id = data["id"]
    assert data["status"] in ["completed", "paused"]

    # 2. List runs via GET /api/v1/runs
    list_res = client.get("/api/v1/runs?workspace_id=1")
    assert list_res.status_code == 200
    runs = list_res.json()
    assert len(runs) >= 1
    assert any(r["id"] == run_id for r in runs)

    # 3. Get single run via GET /api/v1/runs/{id}
    get_res = client.get(f"/api/v1/runs/{run_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == run_id

    # 4. Get events timeline via GET /api/v1/runs/{id}/events
    events_res = client.get(f"/api/v1/runs/{run_id}/events")
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 2
    assert events[0]["event_type"] == "run_started"
