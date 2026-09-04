"""
Regression test suite for Independent Audit Verification & Remediation.
Tests:
- AUD-003: Multimodal image path perimeter validation (strictly inside data_dir).
- AUD-004: Idempotency of resume_agent_run on already completed runs.
- AUD-006: Hybrid model response parsing for JSON tool blocks in various shapes.
"""

import pytest
import tempfile
from pathlib import Path
from fastapi import HTTPException

from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.engine import resume_agent_run, execute_agent_run
from cognishift.core.tool_schemas import parse_agent_action, ToolCallProposal, FinalAnswer


async def _seed_image_test_agent() -> None:
    """Create the minimum isolated workspace/agent required by image-path tests."""
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (1, 'Image Test Workspace')")
        await db.execute(
            """INSERT OR REPLACE INTO agent_definitions
               (id, workspace_id, name, model_name, allowed_tool_ids, approval_required, knowledge_source_ids)
               VALUES (1, 1, 'Image Boundary Agent', 'llama3.2:3b', '[]', 0, '[]')"""
        )
        await db.commit()


# ---------------------------------------------------------------------------
# AUD-004: Resume Idempotency Test
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aud004_resume_completed_run_strictly_enforces_cas_invariant():
    """
    Verify AUD-004 claim disposition:
    Audit claimed missing idempotency causes unhandled 400.
    Code audit proves this is an intentional P0-4 CAS atomic guarantee:
    Runs in terminal 'completed' status cannot be resumed and must raise 400.
    """
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (999, 'Test WS')")
        await db.execute(
            """INSERT OR REPLACE INTO agent_runs 
               (id, workspace_id, agent_id, status, user_id, result_text, model_name)
               VALUES (99901, 999, 1, 'completed', 'operator', 'Already finished result', 'llama3.2:3b')"""
        )
        await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await resume_agent_run(99901)
    
    assert exc_info.value.status_code == 400
    assert "cannot be resumed from current status 'completed'" in exc_info.value.detail


# ---------------------------------------------------------------------------
# AUD-006: Hybrid Model Response Tool Action Parsing
# ---------------------------------------------------------------------------
def test_aud006_parse_agent_action_tool_key_without_action_field():
    """Verify parsing when model outputs {"tool": "...", "parameters": {...}} without action='tool_call'."""
    raw = '{"tool": "check_pressure", "parameters": {"sensor_id": "PT-101"}}'
    action = parse_agent_action(raw, strict=False)
    assert isinstance(action, ToolCallProposal), f"Expected ToolCallProposal, got {type(action)}"
    assert action.tool_name == "check_pressure"
    assert action.parameters == {"sensor_id": "PT-101"}


def test_aud006_parse_agent_action_tool_name_key():
    """Verify parsing when model outputs {"tool_name": "...", "parameters": {...}}."""
    raw = '{"tool_name": "check_temperature", "parameters": {"sensor_id": "TT-102"}}'
    action = parse_agent_action(raw, strict=False)
    assert isinstance(action, ToolCallProposal), f"Expected ToolCallProposal, got {type(action)}"
    assert action.tool_name == "check_temperature"
    assert action.parameters == {"sensor_id": "TT-102"}


def test_aud006_parse_agent_action_name_key():
    """Verify parsing when model outputs {"action": "tool_call", "name": "check_pressure", "parameters": {"sensor_id": "PT-101"}}."""
    raw = '{"action": "tool_call", "name": "check_pressure", "parameters": {"sensor_id": "PT-101"}}'
    action = parse_agent_action(raw, strict=False)
    assert isinstance(action, ToolCallProposal), f"Expected ToolCallProposal, got {type(action)}"
    assert action.tool_name == "check_pressure"
    assert action.parameters == {"sensor_id": "PT-101"}


def test_aud006_parse_agent_action_markdown_json_block():
    """Verify parsing when model emits tool JSON inside markdown code fence."""
    raw = """Based on the plan, I should inspect the pressure reading now.
```json
{
  "tool": "check_pressure",
  "parameters": {"sensor_id": "PT-101"}
}
```
"""
    action = parse_agent_action(raw, strict=False)
    assert isinstance(action, ToolCallProposal), f"Expected ToolCallProposal, got {type(action)}"
    assert action.tool_name == "check_pressure"


# ---------------------------------------------------------------------------
# AUD-003: Multimodal Image Path Perimeter Validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aud003_image_path_outside_data_dir_raises_security_error():
    """Verify that an image path outside settings.data_dir is rejected with a security error."""
    await _seed_image_test_agent()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        temp_img = Path(f.name)

    try:
        # Outside settings.data_dir must fail the run with security error
        res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="Inspect this external image",
            input_image_path=str(temp_img)
        )
        assert res.status == "failed"
        assert "outside allowed data directory" in (res.error_message or "")
    finally:
        temp_img.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_aud003_image_path_inside_data_dir_permitted():
    """Verify that an image path inside settings.data_dir is accepted without security error."""
    await _seed_image_test_agent()
    test_img = settings.data_dir / "vision_test" / "gauge_pressure_critical_485psi.png"
    if not test_img.exists():
        pytest.skip(f"Test image {test_img} not found")

    res = await execute_agent_run(
        workspace_id=1,
        agent_id=1,
        input_text="Inspect this internal gauge image",
        input_image_path=str(test_img)
    )
    # The run may succeed or fail on model inference depending on mode,
    # but it must NOT fail with a path traversal security error
    assert "outside allowed data directory" not in (res.error_message or "")
