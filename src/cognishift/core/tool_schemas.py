"""Strict Per-Tool Schemas and Agent Action Protocol for CogniShift."""
import json
import re
import logging
from typing import Dict, Any, Optional, List, Literal, Union, Type
from typing_extensions import Annotated
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# 1. CONSTRAINED DOMAIN FIELD TYPES (Strict Industrial Boundary Validation)
# -----------------------------------------------------------------------------
EquipmentIdentifier = Annotated[
    str,
    Field(
        min_length=2,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.:-]+$",
        description="Valid plant equipment identifier (alphanumeric, dash, underscore, dot, colon)"
    )
]

OperationalReason = Annotated[
    str,
    Field(
        min_length=5,
        max_length=500,
        description="Operational justification for industrial action (min 5 chars, max 500 chars)"
    )
]

NetworkHostIdentifier = Annotated[
    str,
    Field(
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.-]+$",
        description="Valid internal hostname or IP address"
    )
]

ServiceNameIdentifier = Annotated[
    str,
    Field(
        min_length=2,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.-]+$",
        description="Valid internal system service name"
    )
]


# -----------------------------------------------------------------------------
# 2. AGENT ACTION DEFINITIONS (The LLM Proposes, Deterministic Policy Decides)
# -----------------------------------------------------------------------------
class ToolCallProposal(BaseModel):
    """The agent proposes to call a registered tool with parameters."""
    action: Literal["tool_call"] = "tool_call"
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reason: str = "Execution of next plan step"


class FinalAnswer(BaseModel):
    """The agent provides the final synthesized result."""
    action: Literal["final_answer"] = "final_answer"
    content: str
    citations: List[str] = Field(default_factory=list)


class ClarificationRequest(BaseModel):
    """The agent requests additional clarification from the human operator."""
    action: Literal["clarification_request"] = "clarification_request"
    question: str


AgentAction = Union[ToolCallProposal, FinalAnswer, ClarificationRequest]


# -----------------------------------------------------------------------------
# 3. PER-TOOL PYDANTIC ARGUMENT SCHEMAS (Strict Bound & Regex Checked)
# -----------------------------------------------------------------------------
class CheckPressureArgs(BaseModel):
    sensor_id: EquipmentIdentifier


class CheckTemperatureArgs(BaseModel):
    sensor_id: EquipmentIdentifier


class RunDiagnosticArgs(BaseModel):
    equipment_id: EquipmentIdentifier


class EmergencyPressureReliefArgs(BaseModel):
    chamber_id: EquipmentIdentifier
    reason: OperationalReason


class RestartComponentArgs(BaseModel):
    component_id: EquipmentIdentifier
    reason: OperationalReason


class CheckNetworkArgs(BaseModel):
    target_host: NetworkHostIdentifier


class RestartServiceArgs(BaseModel):
    service_name: ServiceNameIdentifier


# Workspace File & Artifact Tool Schemas (Used in Phase 3 & 4)
class FileListArgs(BaseModel):
    directory: str = Field(default="", description="Relative directory inside workspace")


class FileReadArgs(BaseModel):
    path: str = Field(..., description="Relative workspace path to read")


class FileWriteArgs(BaseModel):
    path: str = Field(..., description="Relative workspace path to write")
    content: str = Field(..., description="Text or script content to write")


class GenerateApprovalNoteArgs(BaseModel):
    title: str = Field(..., description="Formal title for the approval document")
    findings: List[str] = Field(..., description="Bullet point inspection findings")
    recommendation: str = Field(..., description="Final engineering recommendation")


class RunSandboxScriptArgs(BaseModel):
    script_filename: str = Field(..., description="Script filename inside workspace code/ folder")
    input_files: List[str] = Field(default_factory=list, description="Approved input files to stage")


# Tool Name -> Pydantic Schema mapping
TOOL_SCHEMAS: Dict[str, Type[BaseModel]] = {
    "check_pressure": CheckPressureArgs,
    "check_temperature": CheckTemperatureArgs,
    "run_diagnostic": RunDiagnosticArgs,
    "emergency_pressure_relief": EmergencyPressureReliefArgs,
    "restart_component": RestartComponentArgs,
    "check_network": CheckNetworkArgs,
    "restart_service": RestartServiceArgs,
    "file_list": FileListArgs,
    "file_read": FileReadArgs,
    "file_write": FileWriteArgs,
    "generate_approval_note": GenerateApprovalNoteArgs,
    "run_sandbox_script": RunSandboxScriptArgs,
}


# -----------------------------------------------------------------------------
# 3. DETERMINISTIC CENTRAL RISK POLICY
# -----------------------------------------------------------------------------
HIGH_RISK_TOOLS = {
    "emergency_pressure_relief": "service_interrupting",
    "restart_component": "sensitive",
    "restart_service": "service_interrupting"
}


class ToolValidationResult(BaseModel):
    """Result of deterministic tool call validation."""
    valid: bool
    requires_approval: bool
    risk_level: str
    validated_parameters: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


def validate_proposed_tool_call(
    tool_name: str,
    raw_parameters: Dict[str, Any],
    allowed_tools: List[str]
) -> ToolValidationResult:
    """
    Deterministically validates a proposed tool call:
    1. Verifies tool exists.
    2. Verifies calling agent has permission for this tool.
    3. Validates parameters against tool's dedicated Pydantic schema.
    4. Evaluates Central Risk Policy (HITL pause rule).
    """
    # 1. Existence check
    if tool_name not in TOOL_SCHEMAS:
        return ToolValidationResult(
            valid=False,
            requires_approval=False,
            risk_level="unknown",
            error_message=f"Unknown tool '{tool_name}'. Available tools: {list(TOOL_SCHEMAS.keys())}"
        )

    # 2. Permission check
    if allowed_tools and tool_name not in allowed_tools:
        return ToolValidationResult(
            valid=False,
            requires_approval=False,
            risk_level="forbidden",
            error_message=f"Tool '{tool_name}' is not in the allowed tools list for this agent."
        )

    # 3. Schema validation
    schema_cls = TOOL_SCHEMAS[tool_name]
    try:
        validated_obj = schema_cls.model_validate(raw_parameters)
        validated_dict = validated_obj.model_dump()
    except ValidationError as e:
        error_details = []
        for err in e.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            error_details.append(f"Field '{loc}': {err.get('msg')}")
        return ToolValidationResult(
            valid=False,
            requires_approval=False,
            risk_level="invalid_schema",
            error_message=f"Invalid parameters for tool '{tool_name}': " + "; ".join(error_details)
        )

    # 4. Central Risk Policy evaluation (Deterministic HITL interception)
    is_high_risk = tool_name in HIGH_RISK_TOOLS
    risk_level = HIGH_RISK_TOOLS.get(tool_name, "read_only")

    return ToolValidationResult(
        valid=True,
        requires_approval=is_high_risk,
        risk_level=risk_level,
        validated_parameters=validated_dict
    )


# -----------------------------------------------------------------------------
# 4. ROBUST JSON ACTION PARSER
# -----------------------------------------------------------------------------
def parse_agent_action(model_text: str, strict: bool = False) -> Optional[AgentAction]:
    """
    Extracts and validates a structured AgentAction from model text output.
    Returns ToolCallProposal, FinalAnswer, or ClarificationRequest.
    Returns None if output is empty, whitespace, malformed, or unparseable.
    """
    if not model_text or not model_text.strip():
        return None

    clean_text = model_text.strip()

    # 1. Search for markdown code blocks ```json ... ```
    json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
    candidate_json = json_blocks[0] if json_blocks else None

    # 2. Search for raw JSON object if no code block
    if not candidate_json:
        brace_match = re.search(r"(\{[\s\S]*\})", clean_text)
        if brace_match:
            candidate_json = brace_match.group(1)

    if candidate_json:
        try:
            data = json.loads(candidate_json)
            if isinstance(data, dict):
                action = data.get("action", "")
                if action == "tool_call":
                    tool_name = str(data.get("tool_name") or data.get("tool") or "").strip()
                    if not tool_name:
                        return None
                    return ToolCallProposal(
                        action="tool_call",
                        tool_name=tool_name,
                        parameters=data.get("parameters", {}),
                        reason=data.get("reason", "Autonomous plan execution")
                    )
                elif action == "final_answer":
                    content = data.get("content", "")
                    if not content and strict:
                        return None
                    return FinalAnswer(
                        action="final_answer",
                        content=content,
                        citations=data.get("citations", [])
                    )
                elif action == "clarification_request":
                    return ClarificationRequest(
                        action="clarification_request",
                        question=data.get("question", "")
                    )
                else:
                    return None
        except Exception:
            return None

    # Non-strict prose fallback: require meaningful prose (not markup or braces)
    if not strict and len(clean_text) >= 10 and not clean_text.startswith("<") and not clean_text.startswith("{"):
        citations = list(set(re.findall(r"\[(.*?\|\s*Page\s*\d+)\]", clean_text)))
        return FinalAnswer(content=clean_text, citations=citations)

    return None
