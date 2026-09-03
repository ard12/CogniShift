"""Permanent Adversarial Regression Test Suite for CogniShift.

Enforces permanent defenses against:
1. Explanatory prompt keywords triggering tool execution.
2. Model refusal overridden by parser fallbacks.
3. Unauthenticated API access.
4. Header identity spoofing.
5. Cross-workspace IDOR.
6. Four-Eyes self-approval.
7. Resumption TOCTOU race conditions (tool must execute exactly once).
8. Multi-step iterative plan execution.
9. Execution step bounding (MAX_AGENT_STEPS = 10).
10. Provider failure handling.
"""
import pytest
import json
import asyncio
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from cognishift.app.main import app
from cognishift.app.config import settings
from cognishift.core.engine import parse_tool_call, execute_agent_run, resume_agent_run
from cognishift.app.db.database import get_db, init_db
from cognishift.app.core.auth import LOCAL_CREDENTIAL_STORE, User, verify_four_eyes_approval


@pytest.fixture(autouse=True)
def set_simulated_mode(monkeypatch):
    monkeypatch.setattr(settings, "operating_mode", "simulated")


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'Refinery-1', 'MRPL')")
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (2, 'Refinery-2', 'Tenant 2')")
        await db.execute(
            "INSERT OR IGNORE INTO tool_definitions (id, name, description, risk_level, requires_approval, implementation_key) "
            "VALUES (1, 'check_pressure', 'Check pressure', 'read_only', 0, 'check_pressure')"
        )
        await db.execute(
            "INSERT OR IGNORE INTO tool_definitions (id, name, description, risk_level, requires_approval, implementation_key) "
            "VALUES (2, 'check_temperature', 'Check temperature', 'read_only', 0, 'check_temperature')"
        )
        await db.execute(
            "INSERT OR IGNORE INTO tool_definitions (id, name, description, risk_level, requires_approval, implementation_key) "
            "VALUES (4, 'emergency_pressure_relief', 'Emergency relief', 'service_interrupting', 1, 'emergency_pressure_relief')"
        )
        await db.execute(
            "INSERT OR IGNORE INTO agent_definitions (id, workspace_id, name, description, system_instructions, model_name, approval_required, allowed_tool_ids) "
            "VALUES (1, 1, 'Refinery Agent', 'Refinery agent', 'Instructions', 'llama3.2:3b', 0, '[1, 2, 4]')"
        )
        await db.commit()


# -----------------------------------------------------------------------------
# 1. PROMPT KEYWORD EXECUTION REGRESSION (P0-1)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_adversarial_prompt_keyword_cannot_trigger_tool_execution():
    """
    CRIT-01 REGRESSION:
    User prompt mentions a tool name for explanatory reasons.
    Model returns an explanation.
    System MUST NOT execute any tool.
    """
    user_prompt = "Explain how check_pressure works. Do not run check_pressure."
    model_explanation = "The check_pressure tool samples transducer readings from transmitters."
    
    is_tool, tool_name, params, reason = parse_tool_call(
        response_text=model_explanation,
        allowed_tools=["check_pressure"],
        user_prompt=user_prompt
    )
    assert is_tool is False, "Tool was proposed despite pure explanatory prose!"
    assert tool_name is None

    # End-to-end run verification
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text=user_prompt,
        user_id="operator_sam"
    )
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM run_events WHERE run_id = ? AND event_type = 'tool_executing'", (run_res.id,))
        events = await cursor.fetchall()
        assert len(events) == 0, f"Expected 0 tool executions, but found {len(events)}!"


# -----------------------------------------------------------------------------
# 2. MODEL REFUSAL REGRESSION (P0-1 & P0-2)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_adversarial_model_refusal_prevents_tool_and_approval():
    """
    CRIT-01 REGRESSION:
    User asks about a dangerous tool. Model explicitly refuses.
    System MUST NOT pause for approval or execute the tool.
    """
    user_prompt = "Can we run emergency_pressure_relief on chamber REACTOR-B?"
    model_refusal = "I decline to execute this action. Venting Reactor-B is extremely hazardous."

    is_tool, tool_name, params, reason = parse_tool_call(
        response_text=model_refusal,
        allowed_tools=["emergency_pressure_relief"],
        user_prompt=user_prompt
    )
    assert is_tool is False
    assert tool_name is None

    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Decline to run emergency_pressure_relief on REACTOR-B",
        user_id="operator_sam"
    )
    assert run_res.status == "completed"
    assert run_res.status != "paused"

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM approval_requests WHERE run_id = ?", (run_res.id,))
        approvals = await cursor.fetchall()
        assert len(approvals) == 0, "Approval request was created despite model refusal!"


# -----------------------------------------------------------------------------
# 3. UNAUTHENTICATED API ROUTES REGRESSION (P0-7)
# -----------------------------------------------------------------------------
def test_unauthenticated_api_endpoints_rejected_with_401():
    """
    CRIT-04 REGRESSION:
    Any attempt to call platform management or execution APIs without valid credentials
    must return HTTP 401 Unauthorized.
    """
    client = TestClient(app)

    routes = [
        ("POST", "/api/v1/workspaces", {"name": "Test", "description": "Test"}),
        ("GET", "/api/v1/workspaces", None),
        ("POST", "/api/v1/agents", {"workspace_id": 1, "name": "Agent", "allowed_tool_ids": []}),
        ("GET", "/api/v1/agents", None),
        ("POST", "/api/v1/runs", {"workspace_id": 1, "agent_id": 1, "input_text": "Hi"}),
        ("GET", "/api/v1/runs", None),
        ("GET", "/api/v1/approvals", None),
        ("POST", "/api/v1/runs/1/resume", None),
        ("GET", "/api/v1/knowledge?workspace_id=1", None),
    ]

    for method, path, payload in routes:
        if method == "POST":
            res = client.post(path, json=payload)
        else:
            res = client.get(path)
        assert res.status_code == 401, f"{method} {path} returned {res.status_code}, expected 401 Unauthorized!"


# -----------------------------------------------------------------------------
# 4. HEADER SPOOFING REGRESSION (P0-5)
# -----------------------------------------------------------------------------
def test_header_spoofing_without_valid_credentials_rejected():
    """
    CRIT-05 REGRESSION:
    Supplying forged X-User-Role or X-User-ID headers without a valid server token
    must be completely rejected with 401.
    """
    client = TestClient(app)
    spoofed_headers = {
        "X-User-ID": "fake_admin",
        "X-User-Role": "administrator",
        "X-Allowed-Workspaces": "1,2,3"
    }
    res = client.post("/api/v1/workspaces", json={"name": "Hacked", "description": "Spoofed"}, headers=spoofed_headers)
    assert res.status_code == 401


# -----------------------------------------------------------------------------
# 5. WORKSPACE IDOR REGRESSION (P0-7)
# -----------------------------------------------------------------------------
def test_workspace_idor_cross_tenant_access_blocked():
    """
    P0-7 REGRESSION:
    An authenticated operator from Tenant 2 cannot inspect or mutate Tenant 1 resources.
    """
    client = TestClient(app)
    tenant2_headers = {"Authorization": "Bearer token-tenant2-operator"}

    # Attempt to read Workspace 1
    res1 = client.get("/api/v1/workspaces/1", headers=tenant2_headers)
    assert res1.status_code == 403, f"Expected 403 Forbidden for cross-tenant read, got {res1.status_code}"

    # Attempt to trigger run in Workspace 1
    res2 = client.post(
        "/api/v1/runs",
        json={"workspace_id": 1, "agent_id": 1, "input_text": "Telemetry query"},
        headers=tenant2_headers
    )
    assert res2.status_code == 403, f"Expected 403 Forbidden for cross-tenant run, got {res2.status_code}"


# -----------------------------------------------------------------------------
# 6. FOUR-EYES SELF-APPROVAL REGRESSION (P0-8)
# -----------------------------------------------------------------------------
def test_self_approval_denied_by_four_eyes():
    """
    P0-8 REGRESSION:
    Requester cannot approve their own action even if they possess supervisor credentials.
    """
    requester = "operator_sam"
    approver = User(user_id="operator_sam", role="supervisor")
    with pytest.raises(HTTPException) as exc:
        verify_four_eyes_approval(requester_id=requester, approver=approver)
    assert exc.value.status_code == 403
    assert "cannot approve their own request" in exc.value.detail


# -----------------------------------------------------------------------------
# 7. CONCURRENT RESUME IDEMPOTENCY REGRESSION (P0-4)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_resume_executes_tool_exactly_once():
    """
    CRIT-03 REGRESSION:
    Two simultaneous resume requests against a paused high-risk run MUST execute
    the tool exactly once. The competing request must fail with 409 Conflict.
    """
    # 1. Create a paused run
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Trigger emergency_pressure_relief on REACTOR-B",
        user_id="operator_sam"
    )
    assert run_res.status == "paused"
    run_id = run_res.id

    # 2. Mark approval request as approved in database
    async with get_db() as db:
        await db.execute(
            "UPDATE approval_requests SET status = 'approved', reviewed_by = 'supervisor_jane' WHERE run_id = ?",
            (run_id,)
        )
        await db.commit()

    # 3. Track tool executions
    tool_exec_count = 0
    from cognishift.core import engine
    real_execute_tool = engine.execute_tool

    async def counted_execute_tool(name, params):
        nonlocal tool_exec_count
        tool_exec_count += 1
        await asyncio.sleep(0.05)  # simulate network/actuation delay
        return await real_execute_tool(name, params)

    with patch("cognishift.core.engine.execute_tool", side_effect=counted_execute_tool):
        # Fire two concurrent resume attempts
        results = await asyncio.gather(
            resume_agent_run(run_id),
            resume_agent_run(run_id),
            return_exceptions=True
        )

    # 4. Verify outcomes
    successes = [r for r in results if not isinstance(r, Exception)]
    conflicts = [r for r in results if isinstance(r, HTTPException) and r.status_code == 409]

    assert len(successes) == 1, f"Expected exactly 1 successful resume, got {len(successes)}"
    assert len(conflicts) == 1, f"Expected exactly 1 HTTP 409 Conflict, got {len(conflicts)}"
    assert tool_exec_count == 1, f"TOOL EXECUTED {tool_exec_count} TIMES! DUPLICATE EXECUTION DETECTED!"


# -----------------------------------------------------------------------------
# 8. MULTI-STEP ITERATIVE PLAN EXECUTION REGRESSION (P0-3)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_multi_step_execution_persists_observations_and_steps():
    """
    CRIT-02 REGRESSION:
    An agent tasked with a multi-step objective must iteratively advance through steps
    and persist observations across steps.
    """
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Inspect check_pressure telemetry and complete report",
        user_id="operator_sam"
    )
    assert run_res.status == "completed"

    async with get_db() as db:
        cursor = await db.execute("SELECT structured_plan FROM agent_runs WHERE id = ?", (run_res.id,))
        row = await cursor.fetchone()
        plan_data = json.loads(row["structured_plan"])

        # Verify all planned steps completed with recorded observations
        for step in plan_data["steps"]:
            assert step["status"] == "completed", f"Step #{step['id']} was not completed!"
            assert step["observation"] is not None, f"Step #{step['id']} has no recorded observation!"


# -----------------------------------------------------------------------------
# 9. BOUNDED EXECUTION STEP LIMIT REGRESSION (P0-3)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_step_limit_strictly_enforced_at_max_steps():
    """
    P0-3 REGRESSION:
    Agent loops must terminate at or before MAX_AGENT_STEPS = 10 without runaway recursion.
    """
    from cognishift.core.planner import AgentPlan, PlanStep

    # Run should terminate without infinite loop
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Autonomous multi-step diagnostic review",
        user_id="operator_sam"
    )
    assert run_res.status in ["completed", "failed"]

    async with get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) as count FROM run_events WHERE run_id = ? AND event_type = 'plan_step_started'", (run_res.id,))
        count = (await cursor.fetchone())["count"]
        assert count <= 10, f"Step count {count} exceeded MAX_AGENT_STEPS limit of 10!"


# -----------------------------------------------------------------------------
# 10. PROVIDER FAILURE HANDLING REGRESSION
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_provider_failure_marks_run_failed():
    """
    P0 REGRESSION:
    When model inference encounters a critical network or server crash,
    the run must transition to 'failed' and record the error cleanly.
    """
    from cognishift.core.simulated_provider import SimulatedProvider

    async def crashing_generate(*args, **kwargs):
        raise RuntimeError("Ollama daemon unreachable: connection refused on port 11434")

    with patch.object(SimulatedProvider, "generate_text", side_effect=crashing_generate):
        run_res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="Diagnostic check",
            user_id="operator_sam"
        )
        assert run_res.status == "failed"
        assert "Ollama daemon unreachable" in (run_res.error_message or "")
