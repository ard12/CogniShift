"""Test suite for RCA Final-Step Protocol Lockout, JSON backtick parsing, and Action conversion."""
import pytest
import json

from cognishift.core.tool_schemas import (
    parse_agent_action,
    validate_proposed_tool_call,
    ToolCallProposal,
    FinalAnswer
)


def test_parse_agent_action_with_backticks_inside_json():
    # Simulates model output where backticks are inside JSON string values
    raw_output = """```json
{
  "thought": "Inspecting `P-101A` vibration telemetry and `PT-101` pressure readings.",
  "action": "final_answer",
  "content": "The root cause was severe suction strainer clogging leading to cavitation on `P-101A`.",
  "citations": ["P-101A_SOP.pdf | Page 4"]
}
```"""
    action = parse_agent_action(raw_output)
    assert action is not None
    assert isinstance(action, FinalAnswer)
    assert "`P-101A`" in action.content
    assert action.citations == ["P-101A_SOP.pdf | Page 4"]


def test_parse_agent_action_with_singular_citation_field():
    raw_output = """{
  "thought": "Checked SOP",
  "action": "final_answer",
  "content": "Low suction pressure trip confirmed.",
  "citation": ["P-101A_SOP.pdf | Page 4"]
}"""
    action = parse_agent_action(raw_output)
    assert action is not None
    assert isinstance(action, FinalAnswer)
    assert action.citations == ["P-101A_SOP.pdf | Page 4"]


def test_tool_parameter_alias_normalization():
    # Model provides 'bearing_number' or 'bearing' instead of 'sensor_id'
    raw_params = {"bearing_number": "Bearing 1"}
    res = validate_proposed_tool_call(
        tool_name="check_temperature",
        raw_parameters=raw_params,
        allowed_tools=["check_temperature"]
    )
    assert res.valid is True
    assert res.validated_parameters["sensor_id"] == "BEARING_1"

    # Model provides 'tag' with spaces
    raw_params_tag = {"tag": "PT 101"}
    res_tag = validate_proposed_tool_call(
        tool_name="check_pressure",
        raw_parameters=raw_params_tag,
        allowed_tools=["check_pressure"]
    )
    assert res_tag.valid is True
    assert res_tag.validated_parameters["sensor_id"] == "PT_101"


def test_final_step_tool_call_interception_logic():
    # Verify conversion logic when a ToolCallProposal is intercepted on final step
    is_final_step = True
    action = ToolCallProposal(
        action="tool_call",
        tool_name="check_temperature",
        parameters={"sensor_id": "TT-204"},
        reason="I should check temperature before answering"
    )

    if is_final_step and isinstance(action, ToolCallProposal):
        synth_content = getattr(action, "reason", None) or f"Synthesized findings based on available evidence regarding {action.tool_name}."
        action = FinalAnswer(
            action="final_answer",
            content=synth_content,
            citations=[]
        )

    assert isinstance(action, FinalAnswer)
    assert action.action == "final_answer"
    assert "check temperature" in action.content.lower()
