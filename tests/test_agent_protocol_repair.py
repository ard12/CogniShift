import json
import pytest
from unittest.mock import patch
from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.engine import execute_agent_run
from cognishift.core.providers import ModelResponse
from cognishift.core.simulated_provider import SimulatedProvider
from cognishift.core.tool_schemas import parse_agent_action, FinalAnswer


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


@pytest.mark.asyncio
async def test_protocol_repair_with_production_final_answer_schema():
    """
    Regression test:
    - Initial response is malformed / unparseable action JSON.
    - Repair prompt instructs the model to use the production AgentAction schema (action: final_answer).
    - Repair response follows the supplied final-answer schema.
    - parse_agent_action returns FinalAnswer.
    - Run completes successfully.
    """
    malformed_initial = json.dumps({
        "action": "corrupted_or_invalid_action",
        "thought": "This action type does not conform to any valid AgentAction schema."
    })
    valid_repair_answer = json.dumps({
        "thought": "Recovering from malformed output by conforming to final_answer schema.",
        "action": "final_answer",
        "content": "Root cause verified: bearing failure on P-101A due to lubrication starvation.",
        "citations": ["P-101A_Inspection_Report.pdf | Page 2"]
    })

    captured_prompts = []

    async def mock_generate_text(self, prompt, system_prompt="", model_name=None, **kwargs):
        captured_prompts.append(prompt)
        if len(captured_prompts) == 1:
            return ModelResponse(text=malformed_initial, model_name="test", provider="test")
        return ModelResponse(text=valid_repair_answer, model_name="test", provider="test")

    with patch.object(SimulatedProvider, "generate_text", side_effect=mock_generate_text, autospec=True):
        res = await execute_agent_run(
            workspace_id=1,
            agent_id=1,
            input_text="What is pump P-101A?",
            user_id="operator_sam"
        )

    # 1. Verify repair prompt was dispatched and uses the ACTUAL production AgentAction schema
    assert len(captured_prompts) >= 2, f"Expected at least 2 LLM calls, got {len(captured_prompts)}"
    repair_prompt = captured_prompts[1]
    assert '"action": "final_answer"' in repair_prompt, "Repair prompt must instruct action: final_answer"
    assert '"action": "final_response"' not in repair_prompt, "Repair prompt must NOT instruct action: final_response"
    assert '"content": "<your complete final answer>"' in repair_prompt
    assert '"citations": []' in repair_prompt

    # 2. Verify parse_agent_action on the repair response returns FinalAnswer
    parsed = parse_agent_action(valid_repair_answer)
    assert isinstance(parsed, FinalAnswer), "parse_agent_action must return FinalAnswer"
    assert parsed.action == "final_answer"
    assert "Root cause verified" in parsed.content

    # 3. Verify parse_agent_action does NOT accept 'final_response' as an action
    invalid_schema_answer = json.dumps({
        "action": "final_response",
        "answer": "This should not be parsed as FinalAnswer without alias."
    })
    parsed_invalid = parse_agent_action(invalid_schema_answer)
    assert not isinstance(parsed_invalid, FinalAnswer), "parse_agent_action must NOT accept final_response"

    # 4. Verify run completed successfully
    assert res.status == "completed", f"Run failed with status {res.status}: {res.error_message}"
    assert "Root cause verified: bearing failure on P-101A" in res.result_text
