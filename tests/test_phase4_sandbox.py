"""
CogniShift Phase 4 Sandbox Security & Orchestration Test Suite (Tier A).
Tests strict schema bounds, input staging security, hostile output validation,
deterministic simulation, fail-closed container unavailable policy, and bounded retry loops.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, AsyncMock

from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.security import (
    resolve_workspace_path,
    get_workspace_root,
    SecurityError
)
from cognishift.core.tool_schemas import (
    ExecuteCodeArgs,
    SandboxInputReference,
    validate_proposed_tool_call,
    TOOL_SCHEMAS
)
from cognishift.core.sandbox.schemas import (
    CodeExecutionRequest,
    SandboxInputFile,
    SandboxStatus,
    SandboxUnavailableError
)
from cognishift.core.sandbox.staging import (
    stage_execution_environment,
    cleanup_staging_environment
)
from cognishift.core.sandbox.backend import (
    DockerPodmanBackend,
    SimulatedSandboxBackend,
    get_sandbox_backend
)
from cognishift.core.sandbox.promoter import (
    validate_and_promote_outputs,
    ALLOWED_OUTPUT_EXTENSIONS,
    PROHIBITED_OUTPUT_EXTENSIONS
)
from cognishift.core.sandbox.service import execute_sandbox_code
from cognishift.core.engine import execute_agent_run
from cognishift.core.providers import ModelResponse
from cognishift.core.simulated_provider import SimulatedProvider


@pytest.fixture(autouse=True)
def ensure_simulated_mode(monkeypatch):
    monkeypatch.setattr(settings, "operating_mode", "simulated")


@pytest.fixture(autouse=True)
async def initialize_isolated_sandbox_database():
    """Provide the minimum relational context without relying on live seed data."""
    await init_db()
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'Sandbox Test', 'Isolated pytest workspace')"
        )
        await db.execute(
            "INSERT OR IGNORE INTO agent_runs (id, workspace_id, agent_id, status, user_id) VALUES (10, 1, 1, 'completed', 'test_operator')"
        )
        await db.commit()


# -----------------------------------------------------------------------------
# 1. STRICT SCHEMA BOUNDS TESTS
# -----------------------------------------------------------------------------

def test_sandbox_schema_rejects_empty_code():
    with pytest.raises(Exception):
        ExecuteCodeArgs(code="")


def test_sandbox_schema_rejects_oversized_code():
    oversized = "a = 1\n" * 25000  # > 100,000 characters
    with pytest.raises(Exception):
        ExecuteCodeArgs(code=oversized)


@pytest.mark.parametrize("bad_entrypoint", [
    "../evil.py",
    "../../main.py",
    "sub/main.py",
    "main.sh",
    "script.exe",
    "main.py\0",
    "main"
])
def test_sandbox_schema_rejects_invalid_entrypoint(bad_entrypoint):
    with pytest.raises(Exception):
        ExecuteCodeArgs(code="print(1)", entrypoint=bad_entrypoint)


@pytest.mark.parametrize("bad_timeout", [0, 4, 121, -10])
def test_sandbox_schema_rejects_out_of_bounds_timeout(bad_timeout):
    with pytest.raises(Exception):
        ExecuteCodeArgs(code="print(1)", timeout_seconds=bad_timeout)


# -----------------------------------------------------------------------------
# 2. SECURE INPUT STAGING & SUBSYSTEM ISOLATION TESTS
# -----------------------------------------------------------------------------

def test_staging_valid_inputs():
    ws_id = 1
    ws_root = get_workspace_root(ws_id)
    doc_file = ws_root / "documents" / "valid_data.csv"
    doc_file.parent.mkdir(parents=True, exist_ok=True)
    doc_file.write_text("a,b,c\n1,2,3", encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="test_stage_01",
        workspace_id=ws_id,
        run_id=1,
        code="print('hello')",
        entrypoint="main.py",
        input_files=[SandboxInputFile(source_path="documents/valid_data.csv", dest_name="input.csv")]
    )

    stage_dir = stage_execution_environment(ws_id, "test_stage_01", req)
    try:
        assert (stage_dir / "source" / "main.py").exists()
        assert (stage_dir / "source" / "main.py").read_text() == "print('hello')"
        assert (stage_dir / "input" / "input.csv").exists()
        assert (stage_dir / "input" / "input.csv").read_text() == "a,b,c\n1,2,3"
        assert (stage_dir / "output").is_dir()
    finally:
        cleanup_staging_environment(stage_dir)
        assert not stage_dir.exists()


def test_staging_strictly_rejects_knowledge_subsystem():
    ws_id = 1
    ws_root = get_workspace_root(ws_id)
    k_file = ws_root / "knowledge" / "secret_sop.pdf"
    k_file.parent.mkdir(parents=True, exist_ok=True)
    k_file.write_text("SECRET", encoding="utf-8")

    req = CodeExecutionRequest(
        execution_id="test_stage_k",
        workspace_id=ws_id,
        run_id=1,
        code="print(1)",
        input_files=[SandboxInputFile(source_path="knowledge/secret_sop.pdf", dest_name="sop.pdf")]
    )

    with pytest.raises(SecurityError) as exc:
        stage_execution_environment(ws_id, "test_stage_k", req)
    assert "forbidden subsystem 'knowledge/'" in str(exc.value)


def test_staging_strictly_rejects_path_traversal():
    ws_id = 1
    req = CodeExecutionRequest(
        execution_id="test_stage_trav",
        workspace_id=ws_id,
        run_id=1,
        code="print(1)",
        input_files=[SandboxInputFile(source_path="../../data/private/auth_store.json", dest_name="stolen.json")]
    )

    with pytest.raises(SecurityError):
        stage_execution_environment(ws_id, "test_stage_trav", req)


# -----------------------------------------------------------------------------
# 3. SIMULATED BACKEND EXECUTES ZERO CODE
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simulated_backend_executes_zero_code(tmp_path):
    backend = SimulatedSandboxBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "output").mkdir()

    req = CodeExecutionRequest(
        execution_id="exec_safe",
        workspace_id=1,
        run_id=1,
        code="import os; os.remove('important_file.txt')",
        entrypoint="main.py"
    )

    res = await backend.execute(req, staging_dir)
    assert res.status == SandboxStatus.SUCCESS
    assert res.exit_code == 0
    assert "[SIMULATED SANDBOX]" in res.stdout


@pytest.mark.asyncio
async def test_simulated_backend_trigger_runtime_error(tmp_path):
    backend = SimulatedSandboxBackend()
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "output").mkdir()

    req = CodeExecutionRequest(
        execution_id="exec_err",
        workspace_id=1,
        run_id=1,
        code="print(1/0) # ZeroDivisionError",
        entrypoint="main.py"
    )

    res = await backend.execute(req, staging_dir)
    assert res.status == SandboxStatus.RUNTIME_ERROR
    assert res.exit_code == 1
    assert "ZeroDivisionError" in res.stderr


# -----------------------------------------------------------------------------
# 4. HOSTILE OUTPUT VALIDATION & ARTIFACT PROMOTION
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_output_validation_rejects_executable_scripts(tmp_path):
    out_dir = tmp_path / "output"
    out_dir.mkdir()

    # Create malicious outputs
    (out_dir / "payload.py").write_text("import os; os.system('echo hack')", encoding="utf-8")
    (out_dir / "backdoor.sh").write_text("#!/bin/bash\nrm -rf /", encoding="utf-8")
    (out_dir / "malware.exe").write_bytes(b"MZ\x90\x00")
    (out_dir / "report.csv").write_text("Sensor,Reading\nPT-101,102.5", encoding="utf-8")

    promoted_names, promoted_ids = await validate_and_promote_outputs(
        workspace_id=1,
        run_id=10,
        execution_id="sbx_prom_01",
        output_dir=out_dir
    )

    # Only safe deliverable report.csv should be promoted
    assert "payload.py" not in promoted_names
    assert "backdoor.sh" not in promoted_names
    assert "malware.exe" not in promoted_names
    assert "report.csv" in promoted_names
    assert len(promoted_ids) == 1


# -----------------------------------------------------------------------------
# 5. FAIL-CLOSED WHEN CONTAINER RUNTIME IS UNAVAILABLE
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_docker_backend_fails_closed_when_unavailable(tmp_path):
    backend = DockerPodmanBackend(runtime="nonexistent_docker_binary_xyz")
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()

    req = CodeExecutionRequest(
        execution_id="exec_fail_closed",
        workspace_id=1,
        run_id=1,
        code="print('hello')",
        entrypoint="main.py"
    )

    with pytest.raises(SandboxUnavailableError) as exc:
        await backend.execute(req, staging_dir)
    assert "Host code execution fallback is strictly prohibited" in str(exc.value)


# -----------------------------------------------------------------------------
# 6. AGENT PERMISSION & ALLOWLIST ENFORCEMENT
# -----------------------------------------------------------------------------

def test_execute_code_denied_with_empty_allowlist():
    res = validate_proposed_tool_call(
        tool_name="execute_code",
        raw_parameters={"code": "print(1)"},
        allowed_tools=[]
    )
    assert res.valid is False
    assert res.risk_level == "forbidden"


def test_execute_code_denied_when_not_in_allowlist():
    res = validate_proposed_tool_call(
        tool_name="execute_code",
        raw_parameters={"code": "print(1)"},
        allowed_tools=["check_pressure", "check_temperature"]
    )
    assert res.valid is False
    assert res.risk_level == "forbidden"


def test_execute_code_classified_as_sensitive():
    res = validate_proposed_tool_call(
        tool_name="execute_code",
        raw_parameters={"code": "print(1)"},
        allowed_tools=["execute_code"]
    )
    assert res.valid is True
    assert res.risk_level == "sensitive"


@pytest.mark.asyncio
async def test_execute_code_pauses_when_agent_requires_approval():
    await init_db()
    async with get_db() as db:
        await db.execute("""
            INSERT OR REPLACE INTO tool_definitions
            (id, name, description, risk_level, requires_approval, implementation_key)
            VALUES (15, 'execute_code', 'Execute Python Code in Isolated Sandbox', 'sensitive', 0, 'execute_code')
        """)
        await db.execute("""
            INSERT OR REPLACE INTO agent_definitions 
            (id, workspace_id, name, model_name, allowed_tool_ids, approval_required, knowledge_source_ids)
            VALUES (96, 1, 'Supervised Coding Agent', 'llama3.2:3b', '[15]', 1, '[]')
        """)
        await db.commit()

    resp_code = ModelResponse(
        text='''```json
{
  "action": "tool_call",
  "tool_name": "execute_code",
  "parameters": {"code": "print(1)", "entrypoint": "main.py"},
  "reason": "Execute script under supervisor review"
}
```''',
        model_name="llama3.2:3b",
        provider="simulated"
    )

    with patch.object(SimulatedProvider, "generate_text", return_value=resp_code):
        run = await execute_agent_run(workspace_id=1, agent_id=96, input_text="Run script")
        assert run.status == "paused"
        assert "awaiting supervisor approval" in run.result_text


# -----------------------------------------------------------------------------
# 7. CODING AGENT BOUNDED RETRY & DEBUG LOOP
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_coding_agent_retry_loop_bounded():
    await init_db()
    async with get_db() as db:
        await db.execute("""
            INSERT OR REPLACE INTO tool_definitions
            (id, name, description, risk_level, requires_approval, implementation_key)
            VALUES (15, 'execute_code', 'Execute Python Code in Isolated Sandbox', 'sensitive', 0, 'execute_code')
        """)
        await db.execute("""
            INSERT OR REPLACE INTO agent_definitions 
            (id, workspace_id, name, model_name, allowed_tool_ids, approval_required, knowledge_source_ids)
            VALUES (95, 1, 'Buggy Code Agent', 'llama3.2:3b', '[15]', 0, '[]')
        """)
        await db.commit()

    # Tool returns runtime error repeatedly (SIMULATE_RUNTIME_ERROR)
    resp_buggy = ModelResponse(
        text='''```json
{
  "action": "tool_call",
  "tool_name": "execute_code",
  "parameters": {"code": "print(1/0) # SIMULATE_RUNTIME_ERROR", "entrypoint": "main.py"},
  "reason": "Calculate telemetry ratio"
}
```''',
        model_name="llama3.2:3b",
        provider="simulated"
    )

    call_count = 0
    def mock_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return resp_buggy

    with patch.object(SimulatedProvider, "generate_text", side_effect=mock_generate):
        run = await execute_agent_run(workspace_id=1, agent_id=95, input_text="Run calculation")
        print("Run status:", run.status)

    assert run.status in ["completed", "failed"]
    async with get_db() as db:
        c = await db.execute("SELECT event_type FROM run_events WHERE run_id = ? AND event_type LIKE 'sandbox_retry%'", (run.id,))
        events = [r[0] for r in await c.fetchall()]
        assert "sandbox_retry_triggered" in events
        assert "sandbox_retry_exhausted" in events
