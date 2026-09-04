"""Strict Per-Tool Schemas and Agent Action Protocol for CogniShift."""
import json
import re
import logging
from typing import Dict, Any, Optional, List, Literal, Union, Type
from typing_extensions import Annotated
from pydantic import BaseModel, Field, ValidationError, AfterValidator

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


def validate_safe_relative_path(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Relative path cannot be empty.")
    v = v.strip()
    if v.startswith("/") or v.startswith("\\"):
        raise ValueError("Leading slash forbidden in relative path.")
    if ".." in v or "//" in v or "\\\\" in v or "\x00" in v:
        raise ValueError("Path traversal sequences forbidden in relative path.")
    if not re.match(r"^[A-Za-z0-9_.\-\/]+$", v):
        raise ValueError("Invalid characters in relative path.")
    return v


RelativeWorkspacePath = Annotated[
    str,
    AfterValidator(validate_safe_relative_path),
    Field(
        min_length=1,
        max_length=256,
        description="Safe relative path inside workspace"
    )
]


class FileListArgs(BaseModel):
    directory: Optional[RelativeWorkspacePath] = Field(default="documents", description="Relative directory inside workspace (defaults to 'documents')")


class FileReadArgs(BaseModel):
    file_path: RelativeWorkspacePath = Field(..., description="Relative workspace path to read")
    max_bytes: int = Field(default=65536, ge=1, le=1048576, description="Maximum bytes to read (ceiling 1MB)")


class FileWriteArgs(BaseModel):
    file_path: RelativeWorkspacePath = Field(..., description="Relative workspace path to write")
    content: str = Field(..., max_length=500000, description="Text content to write (max 500KB)")
    overwrite: bool = Field(default=False, description="Explicit overwrite flag (default: False)")


class DirectoryCreateArgs(BaseModel):
    directory_path: RelativeWorkspacePath = Field(..., description="Relative directory path to create")


class DocxTable(BaseModel):
    headers: List[str] = Field(..., min_length=1, max_length=15, description="Table column headers")
    rows: List[List[str]] = Field(..., min_length=1, max_length=100, description="Table rows")


class DocxSection(BaseModel):
    heading: str = Field(..., min_length=1, max_length=200, description="Section heading")
    level: int = Field(default=1, ge=1, le=3, description="Heading level 1-3")
    paragraphs: List[str] = Field(default_factory=list, max_length=30, description="Paragraphs in section")
    table: Optional[DocxTable] = Field(None, description="Optional structured table")


class GenerateDocxArgs(BaseModel):
    filename: str = Field(..., pattern=r"^[A-Za-z0-9_.\-]+\.docx$", description="Target filename (must end in .docx)")
    title: str = Field(..., min_length=1, max_length=200, description="Document title")
    sections: List[DocxSection] = Field(..., min_length=1, max_length=50, description="Document sections")


class XlsxRow(BaseModel):
    cells: List[Union[str, int, float, bool]] = Field(..., max_length=30, description="Row cells")


class XlsxSheet(BaseModel):
    name: str = Field(..., min_length=1, max_length=31, pattern=r"^[A-Za-z0-9_ \-]+$", description="Sheet tab name")
    headers: List[str] = Field(..., min_length=1, max_length=30, description="Column headers")
    rows: List[XlsxRow] = Field(..., min_length=1, max_length=500, description="Data rows")


class GenerateXlsxArgs(BaseModel):
    filename: str = Field(..., pattern=r"^[A-Za-z0-9_.\-]+\.xlsx$", description="Target filename (must end in .xlsx)")
    title: str = Field(..., min_length=1, max_length=200, description="Workbook title")
    sheets: List[XlsxSheet] = Field(..., min_length=1, max_length=10, description="Workbook sheets")


class PptxSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Slide title")
    bullet_points: List[str] = Field(..., min_length=1, max_length=10, description="Slide bullet points")


class GeneratePptxArgs(BaseModel):
    filename: str = Field(..., pattern=r"^[A-Za-z0-9_.\-]+\.pptx$", description="Target filename (must end in .pptx)")
    title: str = Field(..., min_length=1, max_length=200, description="Presentation title")
    subtitle: Optional[str] = Field(None, max_length=200, description="Optional subtitle")
    slides: List[PptxSlide] = Field(..., min_length=1, max_length=25, description="Presentation slides")


class SandboxInputReference(BaseModel):
    source_path: str = Field(..., description="Workspace-relative path to input file in documents/ or uploads/")
    dest_name: str = Field(..., pattern=r"^[A-Za-z0-9_.-]+$", description="Destination filename inside sandbox")


class ExecuteCodeArgs(BaseModel):
    code: str = Field(..., min_length=1, max_length=100000, description="Python code to execute inside isolated container")
    entrypoint: str = Field(default="main.py", pattern=r"^[A-Za-z0-9_.-]+\.py$", description="Script entrypoint filename")
    timeout_seconds: int = Field(default=30, ge=5, le=120, description="Execution timeout in seconds")
    input_files: List[SandboxInputReference] = Field(default_factory=list, max_length=10, description="Optional input files")
    promote_outputs_to_artifacts: bool = Field(default=False, description="Promote outputs to permanent artifacts")


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
    "directory_create": DirectoryCreateArgs,
    "generate_docx": GenerateDocxArgs,
    "generate_xlsx": GenerateXlsxArgs,
    "generate_pptx": GeneratePptxArgs,
    "execute_code": ExecuteCodeArgs,
}


# -----------------------------------------------------------------------------
# 3. DETERMINISTIC CENTRAL RISK POLICY
# -----------------------------------------------------------------------------
HIGH_RISK_TOOLS = {
    "emergency_pressure_relief": "service_interrupting",
    "restart_component": "sensitive",
    "restart_service": "service_interrupting"
}

TOOL_RISK_LEVELS = {
    **HIGH_RISK_TOOLS,
    "execute_code": "sensitive",
    "file_write": "low_risk",
    "directory_create": "low_risk",
    "generate_docx": "low_risk",
    "generate_xlsx": "low_risk",
    "generate_pptx": "low_risk",
    "run_diagnostic": "low_risk"
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

    # 2. Permission check (Strict fail-closed allowlist)
    if allowed_tools is not None and (tool_name not in allowed_tools or len(allowed_tools) == 0):
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
    risk_level = TOOL_RISK_LEVELS.get(tool_name, "read_only")

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
                action = str(data.get("action", "")).strip()
                if action == "final_answer":
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

                # Tool call detection: explicit action="tool_call"/"tool",
                # or presence of "tool"/"tool_name"/"function" keys
                tool_candidate = (
                    data.get("tool_name")
                    or data.get("tool")
                    or (data.get("function", {}).get("name") if isinstance(data.get("function"), dict) else None)
                    or (data.get("name") if action in ("tool_call", "tool", "") else None)
                )

                if tool_candidate:
                    tool_name = str(tool_candidate).strip()
                    if tool_name:
                        raw_params = (
                            data.get("parameters")
                            or data.get("arguments")
                            or (data.get("function", {}).get("arguments") if isinstance(data.get("function"), dict) else None)
                            or {}
                        )
                        if isinstance(raw_params, str):
                            try:
                                raw_params = json.loads(raw_params)
                            except Exception:
                                raw_params = {}
                        if not isinstance(raw_params, dict):
                            raw_params = {}

                        reason = data.get("reason") or "Autonomous plan execution"
                        return ToolCallProposal(
                            action="tool_call",
                            tool_name=tool_name,
                            parameters=raw_params,
                            reason=reason
                        )
                return None
        except Exception:
            return None

    # Non-strict prose fallback: require meaningful prose (not code blocks, JSON, markup)
    if (
        not strict
        and len(clean_text) >= 15
        and not clean_text.startswith("<")
        and not clean_text.startswith("{")
        and not clean_text.startswith("`")
        and '"action"' not in clean_text
    ):
        citations = list(set(re.findall(r"\[(.*?\|\s*Page\s*\d+)\]", clean_text)))
        return FinalAnswer(content=clean_text, citations=citations)

    return None
