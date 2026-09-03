"""Phase 2A Structured Tool Calling & Strict Schema Validation Tests."""
import pytest
from cognishift.core.tool_schemas import (
    ToolCallProposal,
    FinalAnswer,
    ClarificationRequest,
    parse_agent_action,
    validate_proposed_tool_call,
    CheckPressureArgs,
    EmergencyPressureReliefArgs
)


def test_parse_tool_call_proposal():
    """Verify that structured JSON tool proposals are parsed cleanly."""
    json_text = """```json
    {
        "action": "tool_call",
        "tool_name": "check_pressure",
        "parameters": {"sensor_id": "PT-101"},
        "reason": "Verify suction pressure"
    }
    ```"""
    action = parse_agent_action(json_text)
    assert isinstance(action, ToolCallProposal)
    assert action.action == "tool_call"
    assert action.tool_name == "check_pressure"
    assert action.parameters == {"sensor_id": "PT-101"}
    assert action.reason == "Verify suction pressure"


def test_parse_final_answer():
    """Verify that final answers with citations are extracted."""
    json_text = """{
        "action": "final_answer",
        "content": "Pump suction pressure is nominal at 4.2 bar [OISD-156 | Page 12].",
        "citations": ["OISD-156 | Page 12"]
    }"""
    action = parse_agent_action(json_text)
    assert isinstance(action, FinalAnswer)
    assert action.action == "final_answer"
    assert "4.2 bar" in action.content
    assert "OISD-156 | Page 12" in action.citations


def test_parse_plain_text_fallback():
    """Verify that unstructured prose gracefully converts to a FinalAnswer."""
    prose = "The hydrocracker unit is operating within normal safety margins."
    action = parse_agent_action(prose)
    assert isinstance(action, FinalAnswer)
    assert action.content == prose


def test_validate_tool_call_valid():
    """Verify that schema-compliant parameters pass validation."""
    result = validate_proposed_tool_call(
        tool_name="check_pressure",
        raw_parameters={"sensor_id": "PT-101"},
        allowed_tools=["check_pressure", "check_temperature"]
    )
    assert result.valid is True
    assert result.requires_approval is False
    assert result.risk_level == "read_only"
    assert result.validated_parameters == {"sensor_id": "PT-101"}
    assert result.error_message is None


def test_validate_tool_call_missing_parameters():
    """Verify that missing required arguments fail Pydantic validation."""
    result = validate_proposed_tool_call(
        tool_name="check_pressure",
        raw_parameters={},  # Missing sensor_id!
        allowed_tools=["check_pressure"]
    )
    assert result.valid is False
    assert result.risk_level == "invalid_schema"
    assert "sensor_id" in result.error_message
    assert "Field required" in result.error_message


def test_validate_tool_call_permission_denied():
    """Verify that tools not on the agent's allowlist are blocked."""
    result = validate_proposed_tool_call(
        tool_name="emergency_pressure_relief",
        raw_parameters={"chamber_id": "V-102", "reason": "test"},
        allowed_tools=["check_pressure"]  # emergency_pressure_relief NOT allowed!
    )
    assert result.valid is False
    assert result.risk_level == "forbidden"
    assert "not in the allowed tools list" in result.error_message


def test_central_risk_policy_forces_hitl():
    """
    CRITICAL ARCHITECTURAL TEST:
    The LLM does NOT ask for approval. The deterministic Central Risk Policy
    intercepts hazardous tools and mandates approval regardless of model intent.
    """
    result = validate_proposed_tool_call(
        tool_name="emergency_pressure_relief",
        raw_parameters={"chamber_id": "V-102", "reason": "Overpressure surge detected"},
        allowed_tools=["emergency_pressure_relief", "check_pressure"]
    )
    assert result.valid is True
    # Central Risk Policy intercepts:
    assert result.requires_approval is True
    assert result.risk_level == "service_interrupting"

    # Also test sensitive restart_component tool
    restart_res = validate_proposed_tool_call(
        tool_name="restart_component",
        raw_parameters={"component_id": "P-101A", "reason": "Vibration anomaly"},
        allowed_tools=["restart_component"]
    )
    assert restart_res.valid is True
    assert restart_res.requires_approval is True
    assert restart_res.risk_level == "sensitive"
