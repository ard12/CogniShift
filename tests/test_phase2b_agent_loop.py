"""Phase 2B Bounded Multi-Step Planner & Resumable Plan State Tests."""
import pytest
import json
from cognishift.core.planner import (
    create_initial_plan,
    format_plan_for_prompt,
    serialize_plan,
    deserialize_plan,
    AgentPlan,
    PlanStep
)
from cognishift.core.engine import execute_agent_run, resume_agent_run
from cognishift.app.db.database import get_db, init_db


from cognishift.app.config import settings


@pytest.fixture(autouse=True)
def set_simulated_mode(monkeypatch):
    """Ensure tests run cleanly in simulated mode without requiring active Ollama."""
    monkeypatch.setattr(settings, "operating_mode", "simulated")


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'MRPL Refinery', 'Test')")
        await db.execute(
            "INSERT OR IGNORE INTO tool_definitions (id, name, description, risk_level, requires_approval, implementation_key) VALUES (4, 'emergency_pressure_relief', 'Emergency vent', 'service_interrupting', 1, 'emergency_pressure_relief')"
        )
        await db.execute(
            "INSERT OR IGNORE INTO agent_definitions (id, workspace_id, name, description, system_instructions, model_name, approval_required, allowed_tool_ids) VALUES (1, 1, 'Safety Agent', 'Safety', 'Inst', 'llama3.2:3b', 0, '[4]')"
        )
        await db.commit()


def test_plan_creation_bounded_to_max_steps():
    """Verify that plans are strictly bounded to <= 10 steps."""
    plan = create_initial_plan("Analyze vibration and generate report", task_type="document_analysis")
    assert isinstance(plan, AgentPlan)
    assert len(plan.steps) <= 10
    assert plan.max_steps == 10
    assert plan.steps[0].status == "pending"


def test_plan_serialization_roundtrip():
    """Verify lossless serialization and deserialization of plan state."""
    plan = create_initial_plan("Stage script and run", task_type="coding")
    plan.steps[0].status = "completed"
    plan.steps[0].observation = "Input files staged successfully"
    plan.advance_to_next_step()

    serialized = serialize_plan(plan)
    restored = deserialize_plan(serialized)

    assert restored is not None
    assert restored.goal == plan.goal
    assert restored.current_step_index == 1
    assert restored.steps[0].status == "completed"
    assert restored.steps[0].observation == "Input files staged successfully"


@pytest.mark.asyncio
async def test_plan_preservation_across_hitl_pause_and_resumption():
    """
    CRITICAL TEST:
    1. Plan is created and saved upon run execution.
    2. Step is marked 'waiting_for_approval' when high-risk tool is intercepted.
    3. On supervisor approval, step is restored, ACTUALLY EXECUTED, and marked 'completed'.
    4. Observation is recorded in the plan step.
    """
    # 1. Trigger high-risk run
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Emergency: emergency_pressure_relief on chamber V-102",
        user_id="operator_sam"
    )
    assert run_res.status == "paused"
    run_id = run_res.id

    # 2. Verify structured_plan exists in database and contains waiting_for_approval
    async with get_db() as db:
        cursor = await db.execute("SELECT structured_plan FROM agent_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        assert row is not None
        plan = deserialize_plan(row["structured_plan"])
        assert plan is not None

        # Verify waiting_for_approval state
        waiting_steps = [s for s in plan.steps if s.status == "waiting_for_approval"]
        assert len(waiting_steps) == 1
        assert waiting_steps[0].tool_name == "emergency_pressure_relief"

        # Approve the request in DB
        cursor_req = await db.execute("SELECT id FROM approval_requests WHERE run_id = ?", (run_id,))
        req_row = await cursor_req.fetchone()
        await db.execute(
            "UPDATE approval_requests SET status = 'approved', reviewed_by = 'supervisor_jane' WHERE id = ?",
            (req_row["id"],)
        )
        await db.commit()

    # 3. Resume the run
    resumed_res = await resume_agent_run(run_id)
    assert resumed_res.status == "completed"

    # 4. Verify plan step transitioned to 'completed' and tool actually executed
    async with get_db() as db:
        cursor = await db.execute("SELECT structured_plan FROM agent_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        resumed_plan = deserialize_plan(row["structured_plan"])
        assert resumed_plan is not None

        # The step must now be completed!
        completed_tool_steps = [
            s for s in resumed_plan.steps
            if s.tool_name == "emergency_pressure_relief" and s.status == "completed"
        ]
        assert len(completed_tool_steps) == 1
        assert completed_tool_steps[0].observation is not None
        assert "EMERGENCY RELIEF EXECUTED" in completed_tool_steps[0].observation
