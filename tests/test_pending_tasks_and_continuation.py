"""Exhaustive Regression Suite for P0 Agent Continuation & Tool Schema Integrity.

Tests cover:
1. Direct low-risk execution without redundant confirmation
2. Affirmation-based continuation with atomic CAS claim
3. Cancellation handling without tool execution
4. Negation guard intercepting commands like 'Do not restart P-101A'
5. Stale task expiration rejection (TTL enforcement)
6. Single-winner atomic CAS concurrency control
7. Zero schema drift across all 14 authoritative tool schemas
8. Deterministic bounded parameter repair from user reference
9. Unsupported equipment target rejection (K-203)
10. Preservation of Four-Eyes dual approval for sensitive tools
"""

import asyncio
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.engine import execute_agent_run
from cognishift.core.providers import ModelResponse
from cognishift.core.simulated_provider import SimulatedProvider
from cognishift.core.pending_tasks import (
    create_pending_task,
    get_active_pending_task,
    get_pending_task,
    claim_pending_task_atomic,
    cancel_pending_task,
    complete_pending_task,
    detect_affirmation_or_cancellation,
    TaskStatus,
)
from cognishift.core.tool_schemas import (
    TOOL_SCHEMAS,
    get_authoritative_tool_json_schema,
    bounded_repair_tool_parameters,
    is_supported_equipment_target,
    SUPPORTED_SIMULATED_TARGETS,
)
from cognishift.core.semantic_router import (
    get_semantic_router,
    SemanticIntent,
    SemanticRoutingResult,
    RoutingReferences,
)
from cognishift.core.conversation_context import (
    ConversationContextResolver,
    get_latest_ingested_document,
)


@pytest.mark.asyncio
async def test_task_store_rejects_expired_claim_and_foreign_cancellation():
    expired = await create_pending_task(1, 'operator_sam', 'CODE_EXECUTION', 'test only', ttl_seconds=-1)
    assert not await claim_pending_task_atomic(expired.id, 1, 'operator_sam')
    live = await create_pending_task(1, 'operator_sam', 'CODE_EXECUTION', 'test only')
    assert not await cancel_pending_task(live.id, 'another_user')
    assert not await claim_pending_task_atomic(live.id, 1, 'admin_rohit')
    assert (await get_pending_task(live.id)).status == TaskStatus.AWAITING_CONFIRMATION
    assert await cancel_pending_task(live.id, 'operator_sam')


@pytest.fixture(autouse=True)
def set_simulated_mode(monkeypatch):
    monkeypatch.setattr(settings, "operating_mode", "simulated")


@pytest.fixture(autouse=True)
async def setup_regression_db():
    """Ensure database is seeded with workspace 1, agent 1, and knowledge source."""
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'MRPL Refinery Operations', 'MRPL')")
        
        # Tools
        tools = [
            (1, 'check_pressure', 'Check Pressure Reading', 'read_only', 0, 1, 'check_pressure'),
            (2, 'check_temperature', 'Check Temperature Reading', 'read_only', 0, 1, 'check_temperature'),
            (3, 'run_diagnostic', 'Run Equipment Diagnostic', 'low_risk', 0, 1, 'run_diagnostic'),
            (4, 'emergency_pressure_relief', 'Emergency Pressure Relief', 'service_interrupting', 1, 1, 'emergency_pressure_relief'),
            (5, 'restart_component', 'Restart System Component', 'sensitive', 1, 1, 'restart_component'),
            (6, 'execute_code', 'Execute Python Code in Sandbox', 'read_only', 0, 1, 'execute_code'),
            (7, 'generate_docx', 'Generate Word Document Report', 'read_only', 0, 1, 'generate_docx'),
            (8, 'file_read', 'Read Local Operational File', 'read_only', 0, 1, 'file_read'),
        ]
        for t in tools:
            await db.execute(
                "INSERT INTO tool_definitions (id, name, description, risk_level, requires_approval, enabled, implementation_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, risk_level=excluded.risk_level, requires_approval=excluded.requires_approval, enabled=excluded.enabled",
                t
            )

        # Agent with all tools enabled
        await db.execute("""
            INSERT INTO agent_definitions 
            (id, workspace_id, name, description, system_instructions, model_name, approval_required, allowed_tool_ids)
            VALUES (1, 1, 'Maintenance Assistant', 'Refinery assistant', 'Industrial guidelines', 'llama3.2:3b', 0, '[1, 2, 3, 4, 5, 6, 7, 8]')
            ON CONFLICT(id) DO UPDATE SET allowed_tool_ids = '[1, 2, 3, 4, 5, 6, 7, 8]', approval_required = 0
        """)

        # Completed knowledge source
        await db.execute("""
            INSERT INTO knowledge_sources (id, workspace_id, name, source_type, original_filename, local_path, processing_status, checksum, chunk_count)
            VALUES (589, 1, 'MRPL OISD 106 PRV SOP', 'pdf', 'MRPL_OISD_106_PRV.pdf', 'data/knowledge/MRPL_OISD_106_PRV.pdf', 'completed', 'sha256_mock_prv_106', 42)
            ON CONFLICT(id) DO UPDATE SET processing_status = 'completed'
        """)
        await db.commit()


# -----------------------------------------------------------------------------
# 1. DIRECT LOW-RISK EXECUTION (No Redundant Confirmation)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_direct_low_risk_execution_runs_without_confirmation():
    """An explicit imperative command to run a Python script and generate a report
    must execute directly via the bounded sandbox workflow without stalling.
    """
    user_prompt = "run a simple python script of your choice that can generate us a report on the latest ingested document"
    
    # Route should deterministically be CODE_EXECUTION
    router = get_semantic_router()
    route_res = router.route(user_prompt)
    assert route_res.intent == SemanticIntent.CODE_EXECUTION
    assert route_res.details.get("rule") == "explicit_code_execution_command"

    # Execute agent run
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text=user_prompt,
        user_id="operator_sam"
    )

    assert run_res.status == "completed"
    assert run_res.error_message is None
    # Verify authoritative backend completion timestamp is attached
    assert "Execution Completed:" in run_res.result_text
    assert "Verified Zero Egress: 100% On-Premise Sovereign Execution" in run_res.result_text

    # Verify structured plan authoritatively resolved document
    plan_data = json.loads(run_res.structured_plan)
    step_descriptions = [s["description"] for s in plan_data["steps"]]
    assert any("MRPL OISD 106 PRV SOP" in desc for desc in step_descriptions)
    assert all(s["status"] == "completed" for s in plan_data["steps"])


# -----------------------------------------------------------------------------
# 2. CONTINUATION SEQUENCE (Affirmation Resumes and Completes Pending Task)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_continuation_sequence_resumes_pending_task():
    """User confirms an awaiting task with 'yea do it and record the time you do it in',
    which claims the task atomically and executes it to completion.
    """
    # 1. Seed an active pending task
    task = await create_pending_task(
        workspace_id=1,
        user_id="operator_sam",
        intent="CODE_EXECUTION",
        requested_goal="Generate summary report from latest ingested document",
        source_references={"document_id": 589, "filename": "MRPL_OISD_106_PRV.pdf"},
        proposed_steps=["Resolve document", "Run sandbox analysis", "Generate docx report"]
    )
    assert task.status == TaskStatus.AWAITING_CONFIRMATION

    # 2. User confirms with affirmation
    followup_prompt = "yea do it and record the time you do it in"
    is_aff, is_canc = detect_affirmation_or_cancellation(followup_prompt)
    assert is_aff is True
    assert is_canc is False

    # Route should identify continuation when active task is present
    resolver = ConversationContextResolver()
    resolved_ctx = resolver.resolve(
        current_turn=followup_prompt,
        conversation_history=[],
        raw_input=followup_prompt,
        workspace_id=1
    )
    assert resolved_ctx.is_affirmation is True

    router = get_semantic_router()
    route_res = router.route(followup_prompt, resolved_context=resolved_ctx, active_pending_task=task)
    assert route_res.intent == SemanticIntent.CODE_EXECUTION
    assert route_res.details.get("resumed_task_id") == task.id

    # Execute
    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text=followup_prompt,
        user_id="operator_sam"
    )

    assert run_res.status == "completed"
    assert "Execution Completed:" in run_res.result_text

    # Verify task was marked COMPLETED in database
    updated_task = await get_pending_task(task.id)
    assert updated_task.status == TaskStatus.COMPLETED
    assert updated_task.resulting_run_id == run_res.id


# -----------------------------------------------------------------------------
# 3. CANCELLATION (Zero Tools Executed)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cancellation_marks_task_cancelled_with_zero_tools():
    """User says 'cancel that', pending task is transitioned to CANCELLED, zero tools executed."""
    task = await create_pending_task(
        workspace_id=1,
        user_id="operator_sam",
        intent="CODE_EXECUTION",
        requested_goal="Generate report on document",
    )

    cancel_prompt = "cancel that"
    is_aff, is_canc = detect_affirmation_or_cancellation(cancel_prompt)
    assert is_canc is True

    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text=cancel_prompt,
        user_id="operator_sam"
    )

    assert run_res.status == "completed"
    assert "cancelled" in run_res.result_text.lower()

    # Task is CANCELLED in DB
    updated_task = await get_pending_task(task.id)
    assert updated_task.status == TaskStatus.CANCELLED


# -----------------------------------------------------------------------------
# 4. NEGATION GUARD (Zero Tools Executed)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_negation_guard_prevents_tool_execution():
    """'Do not restart P-101A' must be safely acknowledged without tool proposals."""
    negation_prompt = "Do not restart P-101A"
    
    router = get_semantic_router()
    route_res = router.route(negation_prompt)
    assert route_res.intent == SemanticIntent.CONVERSATION
    assert route_res.details.get("rule") == "negation_guard"

    run_res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text=negation_prompt,
        user_id="operator_sam"
    )

    assert run_res.status == "completed"
    assert "Acknowledged" in run_res.result_text
    
    # Verify no approval requests created
    async with get_db() as db:
        c = await db.execute("SELECT COUNT(*) as count FROM approval_requests WHERE run_id = ?", (run_res.id,))
        count = (await c.fetchone())["count"]
        assert count == 0


# -----------------------------------------------------------------------------
# 5. STALE TASK REJECTION (TTL Enforcement)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stale_task_ttl_rejection():
    """A task past its TTL expires and is not claimed by affirmations."""
    # Create task with negative TTL (already expired)
    task = await create_pending_task(
        workspace_id=1,
        user_id="operator_sam",
        intent="CODE_EXECUTION",
        requested_goal="Old stale task",
        ttl_seconds=-10
    )
    assert task.is_expired() is True

    # Active pending task query should return None for expired tasks
    active_task = await get_active_pending_task(workspace_id=1, user_id="operator_sam")
    assert active_task is None

    # Affirmation will not claim stale task
    resolver = ConversationContextResolver()
    resolved_ctx = resolver.resolve(
        current_turn="yea go ahead",
        conversation_history=[],
        raw_input="yea go ahead",
        workspace_id=1
    )
    assert resolved_ctx.is_affirmation is True

    router = get_semantic_router()
    route_res = router.route("yea go ahead", resolved_context=resolved_ctx, active_pending_task=None)
    assert route_res.intent == SemanticIntent.CONVERSATION
    assert route_res.details.get("rule") == "stale_or_missing_pending_task"


# -----------------------------------------------------------------------------
# 6. ATOMIC CAS CONCURRENCY CONTROL (Single-Winner)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_atomic_cas_single_winner():
    """Concurrent attempts to claim the same PendingTask yield exactly 1 winner."""
    task = await create_pending_task(
        workspace_id=1,
        user_id="operator_sam",
        intent="CODE_EXECUTION",
        requested_goal="Concurrent claim test",
    )

    # Claim 1 should succeed
    claim1 = await claim_pending_task_atomic(task.id, expected_version=1, claiming_user_id="operator_sam")
    assert claim1 is True

    # Claim 2 with same version should fail (version has bumped to 2)
    claim2 = await claim_pending_task_atomic(task.id, expected_version=1, claiming_user_id="operator_sam")
    assert claim2 is False

    # Claim with wrong user should fail (persona switch safety)
    task2 = await create_pending_task(
        workspace_id=1,
        user_id="operator_sam",
        intent="CODE_EXECUTION",
        requested_goal="Persona test",
    )
    wrong_claim = await claim_pending_task_atomic(task2.id, expected_version=1, claiming_user_id="intruder_bob")
    assert wrong_claim is False


# -----------------------------------------------------------------------------
# 7. ZERO SCHEMA DRIFT ACROSS ALL AUTHORITATIVE TOOL SCHEMAS
# -----------------------------------------------------------------------------
def test_authoritative_tool_schemas_and_zero_drift():
    """Verify all authoritative tools export valid JSON schemas with expected required fields."""
    expected_tools = [
        "check_pressure", "check_temperature", "run_diagnostic",
        "emergency_pressure_relief", "restart_component",
        "check_network", "restart_service",
        "execute_code", "generate_docx", "file_read", "file_list",
        "file_write", "directory_create", "generate_xlsx", "generate_pptx"
    ]
    for tool_name in expected_tools:
        assert tool_name in TOOL_SCHEMAS, f"Missing tool {tool_name} in TOOL_SCHEMAS"
        schema = get_authoritative_tool_json_schema(tool_name)
        assert isinstance(schema, dict)
        assert "properties" in schema

    # Specific schema assertions
    restart_schema = get_authoritative_tool_json_schema("restart_component")
    assert "component_id" in restart_schema["properties"]
    assert "reason" in restart_schema["properties"]
    assert "component_id" in restart_schema["required"]
    assert "reason" in restart_schema["required"]


# -----------------------------------------------------------------------------
# 8. BOUNDED PARAMETER REPAIR FROM USER REFERENCE
# -----------------------------------------------------------------------------
def test_bounded_parameter_repair_from_single_reference():
    """When a tool call omits component_id but user input uniquely identified P-101A,
    bounded repair auto-populates component_id.
    """
    raw_params = {"reason": "Abnormal bearing temperature"}
    refs = RoutingReferences(equipment_ids=["P-101A"])
    repaired, source = bounded_repair_tool_parameters(
        tool_name="restart_component",
        raw_parameters=raw_params,
        references=refs
    )
    assert repaired["component_id"] == "P-101A"
    assert repaired["reason"] == "Abnormal bearing temperature"
    assert source == "USER_REFERENCE"


def test_bounded_parameter_repair_ambiguous_does_not_guess():
    """When multiple equipment references exist, bounded repair refuses to guess."""
    raw_params = {"reason": "Test multiple"}
    refs = RoutingReferences(equipment_ids=["P-101A", "P-101B"])
    repaired, source = bounded_repair_tool_parameters(
        tool_name="restart_component",
        raw_parameters=raw_params,
        references=refs
    )
    assert "component_id" not in repaired
    assert source is None


# -----------------------------------------------------------------------------
# 9. UNSUPPORTED TARGET REJECTION (K-203)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unsupported_target_rejection_k203():
    """Requesting 'Restart K-203 now' is rejected truthfully as UNSUPPORTED
    because K-203 does not exist in refinery topology.
    """
    is_supp, msg = is_supported_equipment_target("K-203")
    assert is_supp is False
    assert "K-203" in msg
    assert "not registered in the refinery topology" in msg

    # Model proposes restart_component with K-203
    model_output = json.dumps({
        "action": "tool_call",
        "tool_name": "restart_component",
        "parameters": {"component_id": "K-203", "reason": "Operator requested restart"},
        "reason": "Restarting K-203 compressor"
    })

    with patch.object(SimulatedProvider, "generate_text", return_value=ModelResponse(text=model_output, model_name="test", provider="test")):
        run_res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="Restart K-203 now.",
            user_id="operator_sam"
        )

    assert run_res.status == "failed"
    assert "Equipment 'K-203' is not registered in the refinery topology" in run_res.result_text
    assert "K-203" in run_res.error_message


# -----------------------------------------------------------------------------
# 10. DUAL AUTHORIZATION PRESERVED FOR SENSITIVE TOOLS
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dual_authorization_preserved_for_p101a():
    """'Restart P-101A now' targets a valid topology component and correctly PAUSES
    for supervisor Four-Eyes approval rather than executing immediately.
    """
    is_supp, _ = is_supported_equipment_target("P-101A")
    assert is_supp is True

    # Even if model emits missing component_id, bounded repair should bind P-101A and pause
    model_output = json.dumps({
        "action": "tool_call",
        "tool_name": "restart_component",
        "parameters": {"reason": "Routine maintenance cycle"},
        "reason": "Restarting P-101A"
    })

    with patch.object(SimulatedProvider, "generate_text", return_value=ModelResponse(text=model_output, model_name="test", provider="test")):
        run_res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="Restart P-101A now.",
            user_id="operator_sam"
        )

    assert run_res.status == "paused"
    assert "Action paused awaiting supervisor approval: restart_component" in run_res.result_text

    # Verify pending approval request exists in DB
    async with get_db() as db:
        c = await db.execute("SELECT * FROM approval_requests WHERE run_id = ?", (run_res.id,))
        req = await c.fetchone()
        assert req is not None
        assert req["status"] == "pending"
        params = json.loads(req["parameters"])
        assert params.get("component_id") == "P-101A"
