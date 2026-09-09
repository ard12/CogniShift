"""Strict Per-Tool Schemas and Agent Action Protocol for CogniShift."""
import json
import re
import logging
from typing import Dict, Any, Optional, List, Literal, Union, Type, Tuple
from typing_extensions import Annotated
from pydantic import BaseModel, Field, ValidationError, AfterValidator, AliasChoices, field_validator

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

    @property
    def answer(self) -> str:
        return self.content


class ClarificationRequest(BaseModel):
    """The agent requests additional clarification from the human operator."""
    action: Literal["clarification_request"] = "clarification_request"
    question: str


class StepObservation(BaseModel):
    """The agent records an intermediate step observation/status without terminating the run."""
    action: Literal["step_observation", "observation"] = "step_observation"
    content: str


AgentAction = Union[ToolCallProposal, FinalAnswer, ClarificationRequest, StepObservation]


# -----------------------------------------------------------------------------
# 3. PER-TOOL PYDANTIC ARGUMENT SCHEMAS (Strict Bound & Regex Checked)
# -----------------------------------------------------------------------------
class CheckPressureArgs(BaseModel):
    sensor_id: EquipmentIdentifier = Field(..., validation_alias=AliasChoices("sensor_id", "sensor", "sensor_name", "equipment_id"))


class CheckTemperatureArgs(BaseModel):
    sensor_id: EquipmentIdentifier = Field(..., validation_alias=AliasChoices("sensor_id", "sensor", "sensor_name", "equipment_id"))


class RunDiagnosticArgs(BaseModel):
    equipment_id: EquipmentIdentifier = Field(..., validation_alias=AliasChoices("equipment_id", "equipment", "component_id", "component", "sensor_id", "sensor"))


class EmergencyPressureReliefArgs(BaseModel):
    chamber_id: EquipmentIdentifier = Field(..., validation_alias=AliasChoices("chamber_id", "chamber", "equipment_id", "component_id"))
    valve_tag: Optional[EquipmentIdentifier] = Field(default="SV-402", validation_alias=AliasChoices("valve_tag", "valve", "valve_id", "tag"))
    reason: OperationalReason = Field(default="Emergency pressure relief intervention")


class RestartComponentArgs(BaseModel):
    component_id: EquipmentIdentifier = Field(..., validation_alias=AliasChoices("component_id", "component_name", "component", "equipment_id"))
    reason: OperationalReason = Field(..., validation_alias=AliasChoices("reason", "justification", "operational_reason"))


class CheckNetworkArgs(BaseModel):
    target_host: NetworkHostIdentifier = Field(..., validation_alias=AliasChoices("target_host", "host", "target", "hostname", "ip"))


class RestartServiceArgs(BaseModel):
    service_name: ServiceNameIdentifier = Field(..., validation_alias=AliasChoices("service_name", "service", "name"))


class CheckInterlockStatusArgs(BaseModel):
    subsystem: EquipmentIdentifier = Field(
        default="P-101A",
        validation_alias=AliasChoices("subsystem", "equipment_id", "component_id", "sensor_id", "system", "component"),
        description="Subsystem or equipment to check interlock status for"
    )


def validate_safe_relative_path(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Relative path cannot be empty.")
    v = v.strip()
    if v.startswith("./") or v.startswith(".\\"):
        v = v[2:]
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
    filename: str = Field(..., pattern=r"^[A-Za-z0-9_.\-]+\.(?i:docx)$", description="Target filename (must end in .docx)")
    title: str = Field(..., min_length=1, max_length=200, description="Document title")
    sections: List[DocxSection] = Field(..., min_length=1, max_length=50, description="Document sections")

    @field_validator("filename", mode="before")
    @classmethod
    def normalize_filename(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.strip().replace("\\", "/").split("/")[-1]
            if not clean:
                return "document.docx"
            if clean.lower().endswith(".docx"):
                clean = clean[:-5] + ".docx"
            else:
                clean = f"{clean}.docx"
            return clean
        return "document.docx"


class XlsxRow(BaseModel):
    cells: List[Union[str, int, float, bool]] = Field(..., max_length=30, description="Row cells")


class XlsxSheet(BaseModel):
    name: str = Field(..., min_length=1, max_length=31, pattern=r"^[A-Za-z0-9_ \-]+$", description="Sheet tab name")
    headers: List[str] = Field(..., min_length=1, max_length=30, description="Column headers")
    rows: List[XlsxRow] = Field(..., min_length=1, max_length=500, description="Data rows")


class GenerateXlsxArgs(BaseModel):
    filename: str = Field(..., pattern=r"^[A-Za-z0-9_.\-]+\.(?i:xlsx)$", description="Target filename (must end in .xlsx)")
    title: str = Field(..., min_length=1, max_length=200, description="Workbook title")
    sheets: List[XlsxSheet] = Field(..., min_length=1, max_length=10, description="Workbook sheets")

    @field_validator("filename", mode="before")
    @classmethod
    def normalize_filename(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.strip().replace("\\", "/").split("/")[-1]
            if not clean:
                return "workbook.xlsx"
            if clean.lower().endswith(".xlsx"):
                clean = clean[:-5] + ".xlsx"
            else:
                clean = f"{clean}.xlsx"
            return clean
        return "workbook.xlsx"


class PptxSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Slide title")
    bullet_points: List[str] = Field(..., min_length=1, max_length=10, description="Slide bullet points")


class GeneratePptxArgs(BaseModel):
    filename: str = Field(..., pattern=r"^[A-Za-z0-9_.\-]+\.(?i:pptx)$", description="Target filename (must end in .pptx)")
    title: str = Field(..., min_length=1, max_length=200, description="Presentation title")
    subtitle: Optional[str] = Field(None, max_length=200, description="Optional subtitle")
    slides: List[PptxSlide] = Field(..., min_length=1, max_length=25, description="Presentation slides")

    @field_validator("filename", mode="before")
    @classmethod
    def normalize_filename(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.strip().replace("\\", "/").split("/")[-1]
            if not clean:
                return "presentation.pptx"
            if clean.lower().endswith(".pptx"):
                clean = clean[:-5] + ".pptx"
            else:
                clean = f"{clean}.pptx"
            return clean
        return "presentation.pptx"


class SandboxInputReference(BaseModel):
    source_path: str = Field(..., description="Workspace-relative path to input file in documents/ or uploads/")
    dest_name: str = Field(..., pattern=r"^[A-Za-z0-9_.-]+$", description="Destination filename inside sandbox")


class ExecuteCodeArgs(BaseModel):
    code: str = Field(..., min_length=1, max_length=100000, description="Python code to execute inside isolated container")
    entrypoint: str = Field(default="main.py", pattern=r"^[A-Za-z0-9_.-]+\.(?i:py)$", description="Script entrypoint filename")
    timeout_seconds: int = Field(default=30, ge=5, le=120, description="Execution timeout in seconds")
    input_files: List[SandboxInputReference] = Field(default_factory=list, max_length=10, description="Optional input files")
    promote_outputs_to_artifacts: bool = Field(default=False, description="Promote outputs to permanent artifacts")

    @field_validator("entrypoint", mode="before")
    @classmethod
    def normalize_entrypoint(cls, v: Any) -> str:
        if isinstance(v, str):
            if "\0" in v or "/" in v or "\\" in v:
                raise ValueError("Entrypoint cannot contain directory separators or null bytes")
            if not v.lower().endswith(".py"):
                raise ValueError("Entrypoint must end with .py")
            return v[:-3] + ".py"
        return "main.py"



class GenerateCsvArgs(BaseModel):
    filename: str = Field(..., pattern=r"^[A-Za-z0-9_.\-]+\.(?i:csv)$", description="Target filename (must end in .csv)")
    title: str = Field(..., min_length=1, max_length=200, description="CSV export title")
    headers: List[str] = Field(default_factory=list, max_length=50, description="CSV column headers")
    rows: List[List[Union[str, int, float, bool, None]]] = Field(default_factory=list, max_length=5000, description="CSV data rows")

    @field_validator("filename", mode="before")
    @classmethod
    def normalize_filename(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.strip().replace("\\", "/").split("/")[-1]
            if not clean:
                return "data.csv"
            if clean.lower().endswith(".csv"):
                clean = clean[:-4] + ".csv"
            else:
                clean = f"{clean}.csv"
            return clean
        return "data.csv"


class GeneratePdfArgs(BaseModel):
    filename: str = Field(..., pattern=r"^[A-Za-z0-9_.\-]+\.(?i:pdf)$", description="Target filename (must end in .pdf)")
    title: str = Field(..., min_length=1, max_length=200, description="Document title")
    sections: List[DocxSection] = Field(..., min_length=1, max_length=50, description="Document sections")

    @field_validator("filename", mode="before")
    @classmethod
    def normalize_filename(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.strip().replace("\\", "/").split("/")[-1]
            if not clean:
                return "document.pdf"
            if clean.lower().endswith(".pdf"):
                clean = clean[:-4] + ".pdf"
            else:
                clean = f"{clean}.pdf"
            return clean
        return "document.pdf"


class RenderDocumentPageArgs(BaseModel):
    source_path_or_id: str = Field(..., description="Path to PDF in workspace documents/ or knowledge source ID")
    page_number: int = Field(default=1, ge=1, le=1000, description="1-indexed page number to render")
    output_filename: str = Field(default="page_1.png", pattern=r"^[A-Za-z0-9_.\-]+\.(?i:png|jpg|jpeg)$", description="Output image filename")
    format: str = Field(default="png", pattern=r"^(?i:png|jpg|jpeg)$", description="Target image format")

    @field_validator("format", mode="before")
    @classmethod
    def normalize_format(cls, v: Any) -> str:
        if isinstance(v, str):
            val = v.strip().lower()
            if val.startswith("."):
                val = val[1:]
            if val.startswith("image/"):
                val = val[6:]
            if val in ("png", "jpg", "jpeg"):
                return val
        return "png"

    @field_validator("output_filename", mode="before")
    @classmethod
    def normalize_output_filename(cls, v: Any) -> str:
        if isinstance(v, str):
            clean = v.strip().replace("\\", "/").split("/")[-1]
            if not clean:
                return "page_1.png"
            for ext in (".png", ".jpg", ".jpeg"):
                if clean.lower().endswith(ext):
                    clean = clean[:-len(ext)] + ext
                    break
            else:
                clean = f"{clean}.png"
            return clean
        return "page_1.png"


# Tool Name -> Pydantic Schema mapping
TOOL_SCHEMAS: Dict[str, Type[BaseModel]] = {
    "check_pressure": CheckPressureArgs,
    "check_temperature": CheckTemperatureArgs,
    "run_diagnostic": RunDiagnosticArgs,
    "emergency_pressure_relief": EmergencyPressureReliefArgs,
    "restart_component": RestartComponentArgs,
    "check_network": CheckNetworkArgs,
    "restart_service": RestartServiceArgs,
    "check_interlock_status": CheckInterlockStatusArgs,
    "file_list": FileListArgs,
    "file_read": FileReadArgs,
    "file_write": FileWriteArgs,
    "directory_create": DirectoryCreateArgs,
    "generate_docx": GenerateDocxArgs,
    "generate_xlsx": GenerateXlsxArgs,
    "generate_pptx": GeneratePptxArgs,
    "generate_pdf": GeneratePdfArgs,
    "generate_csv": GenerateCsvArgs,
    "render_document_page": RenderDocumentPageArgs,
    "execute_code": ExecuteCodeArgs,
}


# -----------------------------------------------------------------------------
# 3. DETERMINISTIC CENTRAL RISK POLICY
# -----------------------------------------------------------------------------
HIGH_RISK_TOOLS = {
    "emergency_pressure_relief": "service_interrupting",
    "restart_component": "sensitive",
    "restart_service": "service_interrupting",
}

TOOL_RISK_LEVELS = {
    **HIGH_RISK_TOOLS,
    "execute_code": "sensitive",

    "check_pressure": "read_only",
    "check_temperature": "read_only",
    "check_network": "read_only",
    "file_list": "read_only",
    "file_read": "read_only",

    "file_write": "low_risk",
    "directory_create": "low_risk",
    "generate_docx": "low_risk",
    "generate_xlsx": "low_risk",
    "generate_pptx": "low_risk",
    "generate_pdf": "low_risk",
    "generate_csv": "low_risk",
    "render_document_page": "low_risk",
    "run_diagnostic": "low_risk",
    "check_interlock_status": "low_risk"
}


SUPPORTED_SIMULATED_TARGETS = {
    "P-101A": "Crude Feed Booster Pump A (API 610 Centrifugal Between-Bearings)",
    "P-101B": "Crude Feed Booster Pump B (Bypass Redundancy)",
    "Reactor-B": "Catalytic Hydrotreater Reactor Vessel (Fixed Bed Downflow)",
    "SV-402": "Pilot-Operated Pressure Relief Valve",
    "TK-01": "Atmospheric Crude Storage Tank",
    "Flare-Header": "High-Pressure Acid Gas Flare Header",
    "PT-101": "Discharge Header Pressure Transmitter",
    "TT-204": "Outboard Journal Bearing Thermocouple",
    "K-101": "Centrifugal Recycle Gas Compressor",
    "M-101": "Induction Drive Motor (6.6 kV)",
    "MOV-101": "Motor-Operated Isolation Valve",
}


EQUIPMENT_ALIASES = {
    "P-101A-PRESS": "PT-101",
    "P-101A_PRESS": "PT-101",
    "P-101A_INLET": "P-101A",
    "P-101A-INLET": "P-101A",
    "CDU-MANIFOLD-PRESSURE-SENSOR": "PT-101",
    "CDU_MANIFOLD_PRESSURE_SENSOR": "PT-101",
    "PRESSURE_SENSOR": "PT-101",
    "PUMP-A": "P-101A",
    "PUMP-B": "P-101B",
    "P-101": "P-101A",
    "P101": "P-101A",
    "XV-201": "SV-402",
    "XV201": "SV-402",
}


CANONICAL_TARGETS = {
    tag.upper(): tag for tag in SUPPORTED_SIMULATED_TARGETS.keys()
}


def resolve_equipment_alias(target_id: str) -> str:
    cleaned = (target_id or "").strip().upper()
    for prefix in ("PUMP ", "SENSOR ", "CHAMBER ", "VALVE ", "VESSEL ", "TRANSMITTER ", "UNIT "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    cleaned = re.sub(r'([A-Za-z0-9]+)\s*-\s*([0-9]+)\s*([A-Za-z])\b', r'\1-\2\3', cleaned)
    cleaned = re.sub(r'([A-Za-z0-9]+)\s*-\s*([0-9]+)\b', r'\1-\2', cleaned)
    resolved = EQUIPMENT_ALIASES.get(cleaned, cleaned)
    return CANONICAL_TARGETS.get(resolved.upper(), resolved)


def is_supported_equipment_target(target_id: str) -> Tuple[bool, str]:
    """Check if target equipment is supported in the simulated plant topology."""
    resolved = resolve_equipment_alias(target_id)
    cleaned = (resolved or "").strip().upper()
    for supported_tag, desc in SUPPORTED_SIMULATED_TARGETS.items():
        if cleaned == supported_tag.upper():
            return True, desc
    supported_list = ", ".join(sorted(SUPPORTED_SIMULATED_TARGETS.keys()))
    return False, f"Equipment '{target_id}' is not registered in the refinery topology. Supported components: {supported_list}."


def get_authoritative_tool_json_schema(tool_name: str) -> Dict[str, Any]:
    """Export single-source-of-truth JSON Schema from authoritative Pydantic model.
    
    Zero schema drift guarantee:
    Prompt generation reads directly from this authoritative schema.
    """
    if tool_name in TOOL_SCHEMAS:
        schema = TOOL_SCHEMAS[tool_name].model_json_schema()
        props = {}
        required = schema.get("required", [])
        for k, v in schema.get("properties", {}).items():
            props[k] = {
                "type": v.get("type", "string"),
                "description": v.get("description", ""),
                "required": k in required
            }
        return {
            "type": "object",
            "properties": props,
            "required": required
        }
    return {"type": "object", "properties": {}}


def bounded_repair_tool_parameters(
    tool_name: str,
    raw_parameters: Dict[str, Any],
    references: Optional[Any] = None
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Deterministic bounded structured argument repair from explicit user references
    and robust parameter normalization.
    
    CRITICAL RULE (P0 Spec 12 & 13):
    Only repairs when unambiguous user reference was explicitly supplied in current turn.
    Returns (repaired_params, argument_source).
    """
    params = dict(raw_parameters)
    arg_source = None

    # Universal parameter hygiene / normalization across all tools
    if tool_name == "render_document_page":
        if "format" in params:
            fmt = str(params["format"]).strip().lower()
            if fmt.startswith("."):
                fmt = fmt[1:]
            if fmt.startswith("image/"):
                fmt = fmt[6:]
            if fmt in ("png", "jpg", "jpeg"):
                params["format"] = fmt
            else:
                params["format"] = "png"
        else:
            params["format"] = "png"

        if "output_filename" in params and isinstance(params["output_filename"], str):
            fname = params["output_filename"].strip().replace("\\", "/").split("/")[-1]
            for ext in (".png", ".jpg", ".jpeg"):
                if fname.lower().endswith(ext):
                    fname = fname[:-len(ext)] + ext
                    break
            else:
                fname = f"{fname}.png"
            params["output_filename"] = fname
        elif "output_filename" not in params:
            page_num = params.get("page_number", 1)
            params["output_filename"] = f"page_{page_num}.png"

        if "page_number" in params:
            try:
                params["page_number"] = int(params["page_number"])
            except (ValueError, TypeError):
                params["page_number"] = 1

    elif tool_name in ("generate_docx", "generate_xlsx", "generate_pptx", "generate_pdf", "generate_csv"):
        ext_map = {
            "generate_docx": ".docx",
            "generate_xlsx": ".xlsx",
            "generate_pptx": ".pptx",
            "generate_pdf": ".pdf",
            "generate_csv": ".csv",
        }
        expected_ext = ext_map[tool_name]
        if "filename" in params and isinstance(params["filename"], str):
            fname = params["filename"].strip().replace("\\", "/").split("/")[-1]
            if fname.lower().endswith(expected_ext):
                fname = fname[:-len(expected_ext)] + expected_ext
            else:
                fname = f"{fname}{expected_ext}"
            params["filename"] = fname
        elif "filename" not in params:
            params["filename"] = f"deliverable{expected_ext}"

        if "title" in params and isinstance(params["title"], str):
            params["title"] = params["title"].strip() or "Operational Deliverable"
        elif "title" not in params:
            params["title"] = "Operational Deliverable"

    elif tool_name == "execute_code":
        if "entrypoint" in params and isinstance(params["entrypoint"], str):
            ep = params["entrypoint"].strip().replace("\\", "/").split("/")[-1]
            if ep.lower().endswith(".py"):
                ep = ep[:-3] + ".py"
            else:
                ep = f"{ep}.py"
            params["entrypoint"] = ep
        elif "entrypoint" not in params:
            params["entrypoint"] = "main.py"

    for eq_key in ("sensor_id", "equipment_id", "component_id", "chamber_id", "subsystem"):
        if eq_key in params and isinstance(params[eq_key], str):
            raw_val = params[eq_key].strip().rstrip(".")
            params[eq_key] = resolve_equipment_alias(raw_val)

    if "file_path" in params and isinstance(params["file_path"], str):
        fp = params["file_path"].strip()
        if fp.startswith("./") or fp.startswith(".\\"):
            fp = fp[2:]
        params["file_path"] = fp

    if references is None:
        return params, None

    # Handle restart_component missing component_id
    if tool_name == "restart_component":
        has_comp = any(params.get(k) for k in ["component_id", "component_name", "component", "equipment_id"])
        if not has_comp:
            eq_ids = getattr(references, "equipment_ids", []) or []
            if len(eq_ids) == 1:
                params["component_id"] = eq_ids[0]
                arg_source = "USER_REFERENCE"
        if not params.get("reason"):
            params["reason"] = "Operational restart requested by plant operator"

    # Handle check_pressure / check_temperature missing sensor_id
    elif tool_name in ("check_pressure", "check_temperature"):
        has_sensor = any(params.get(k) for k in ["sensor_id", "sensor", "sensor_name", "equipment_id"])
        if not has_sensor:
            eq_ids = getattr(references, "equipment_ids", []) or []
            if len(eq_ids) == 1:
                params["sensor_id"] = eq_ids[0]
                arg_source = "USER_REFERENCE"

    # Handle emergency_pressure_relief missing chamber_id
    elif tool_name == "emergency_pressure_relief":
        has_chamber = any(params.get(k) for k in ["chamber_id", "chamber", "equipment_id", "component_id"])
        if not has_chamber:
            eq_ids = getattr(references, "equipment_ids", []) or []
            if len(eq_ids) == 1:
                params["chamber_id"] = eq_ids[0]
                arg_source = "USER_REFERENCE"
        elif "chamber_id" not in params:
            for k in ["chamber", "equipment_id", "component_id"]:
                if k in params:
                    params["chamber_id"] = params.pop(k)
                    break

    # Handle run_diagnostic missing equipment_id
    elif tool_name == "run_diagnostic":
        has_eq = any(params.get(k) for k in ["equipment_id", "equipment", "component_id"])
        if not has_eq:
            eq_ids = getattr(references, "equipment_ids", []) or []
            if len(eq_ids) == 1:
                params["equipment_id"] = eq_ids[0]
                arg_source = "USER_REFERENCE"

    for eq_key in ("sensor_id", "equipment_id", "component_id", "chamber_id", "subsystem"):
        if eq_key in params and isinstance(params[eq_key], str):
            params[eq_key] = resolve_equipment_alias(params[eq_key])

    return params, arg_source


class ToolValidationResult(BaseModel):
    """Result of deterministic tool call validation."""
    valid: bool
    requires_approval: bool
    risk_level: str
    validated_parameters: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    argument_source: Optional[str] = None


def validate_proposed_tool_call(
    tool_name: str,
    raw_parameters: Dict[str, Any],
    allowed_tools: List[str],
    references: Optional[Any] = None
) -> ToolValidationResult:
    """
    Deterministically validates a proposed tool call:
    1. Verifies tool exists.
    2. Verifies calling agent has permission for this tool.
    3. Performs bounded parameter repair from explicit user references if unambiguous.
    4. Validates parameters against tool's dedicated Pydantic schema.
    5. Evaluates Central Risk Policy (HITL pause rule).
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

    # 3. Bounded Parameter Repair
    repaired_params, arg_source = bounded_repair_tool_parameters(tool_name, raw_parameters, references)

    # 4. Schema validation
    schema_cls = TOOL_SCHEMAS[tool_name]
    try:
        validated_obj = schema_cls.model_validate(repaired_params)
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

    # 5. Central Risk Policy evaluation (Deterministic HITL interception)
    is_high_risk = tool_name in HIGH_RISK_TOOLS
    risk_level = TOOL_RISK_LEVELS.get(tool_name, "read_only")

    return ToolValidationResult(
        valid=True,
        requires_approval=is_high_risk,
        risk_level=risk_level,
        validated_parameters=validated_dict,
        argument_source=arg_source
    )


# -----------------------------------------------------------------------------
# 4. ROBUST JSON ACTION PARSER
# -----------------------------------------------------------------------------
def _render_structured_final_content(value: Any, depth: int = 0) -> str:
    """Render an SLM's structured final content as readable, bounded Markdown."""
    if depth > 5:
        return str(value)[:2000]
    if isinstance(value, dict):
        parts: List[str] = []
        for key, item in list(value.items())[:40]:
            label = str(key).replace("_", " ").strip().title()
            if isinstance(item, (dict, list)):
                parts.append(f"{'#' * min(depth + 2, 6)} {label}\n{_render_structured_final_content(item, depth + 1)}")
            else:
                parts.append(f"- **{label}:** {item}")
        return "\n\n".join(parts)
    if isinstance(value, list):
        parts = []
        for item in value[:100]:
            rendered = _render_structured_final_content(item, depth + 1)
            parts.append(rendered if isinstance(item, (dict, list)) else f"- {rendered}")
        return "\n".join(parts)
    return str(value)


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
        # Pre-clean backticks used by SLM as quotation delimiters for string values
        candidate_json_clean = re.sub(r':\s*`([\s\S]*?)`', lambda m: ': ' + json.dumps(m.group(1)), candidate_json)
        try:
            data = json.loads(candidate_json_clean)
            if isinstance(data, dict):
                action = str(data.get("action") or data.get("type") or "").strip().lower()
                if action == "final_answer":
                    content = data.get("content") if data.get("content") is not None else data.get("answer", "")
                    if not content and strict:
                        return None
                    if isinstance(content, (dict, list)):
                        content = _render_structured_final_content(content)
                    return FinalAnswer(
                        action="final_answer",
                        content=str(content),
                        citations=data.get("citations", [])
                    )
                elif action in ("step_observation", "observation"):
                    content = data.get("content") if data.get("content") is not None else data.get("observation", "")
                    return StepObservation(
                        action="step_observation",
                        content=str(content)
                    )
                elif action == "clarification_request":
                    question = data.get("question") if data.get("question") is not None else data.get("content", "")
                    return ClarificationRequest(
                        action="clarification_request",
                        question=str(question)
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

                        # Safeguard: if model wrapped natural explanatory text inside execute_code
                        if tool_name == "execute_code":
                            code_str = str(raw_params.get("code") or raw_params.get("script") or "").strip()
                            python_keywords = ["import ", "def ", "class ", "print(", "=", "return ", "for ", "while ", "try:", "if "]
                            if len(code_str) > 20 and not any(kw in code_str for kw in python_keywords):
                                citations = list(set(re.findall(r"\[([^\]\n]+?\|\s*Page\s*\d+)(?:\s*\|.*?)?\]", code_str)))
                                return FinalAnswer(action="final_answer", content=code_str, citations=citations)

                        reason = data.get("reason") or "Autonomous plan execution"
                        return ToolCallProposal(
                            action="tool_call",
                            tool_name=tool_name,
                            parameters=raw_params,
                            reason=reason
                        )
                if strict:
                    return None
        except Exception:
            # Resilient fallback for SLM outputs with unescaped internal quotes inside JSON strings
            try:
                action_m = re.search(r'"(?:action|type)"\s*:\s*"final_answer"', candidate_json, re.IGNORECASE)
                if action_m:
                    content_m = re.search(r'"(?:content|answer)"\s*:\s*"(.*?)(?:"\s*,\s*"(?:citations|action|type)"|"\s*\})', candidate_json, re.DOTALL)
                    citations_m = re.search(r'"citations"\s*:\s*\[(.*?)\]', candidate_json, re.DOTALL)
                    citations = []
                    if citations_m:
                        citations = [c.strip().strip('"').strip("'") for c in citations_m.group(1).split(",") if c.strip().strip('"').strip("'")]
                    if content_m:
                        return FinalAnswer(
                            action="final_answer",
                            content=content_m.group(1),
                            citations=citations
                        )

                action_obs = re.search(r'"(?:action|type)"\s*:\s*"(?:step_observation|observation)"', candidate_json, re.IGNORECASE)
                if action_obs:
                    content_m = re.search(r'"(?:content|observation)"\s*:\s*"(.*?)(?:"\s*,\s*"|"\s*\})', candidate_json, re.DOTALL)
                    if content_m:
                        return StepObservation(
                            action="step_observation",
                            content=content_m.group(1)
                        )
                
                tool_m = re.search(r'"(?:tool_name|tool)"\s*:\s*"([^"]+)"', candidate_json)
                if tool_m:
                    tool_name = tool_m.group(1).strip()
                    reason_m = re.search(r'"reason"\s*:\s*"(.*?)(?:"\s*,\s*"|"\s*\})', candidate_json, re.DOTALL)
                    reason = reason_m.group(1) if reason_m else "Autonomous plan execution"
                    extracted_params = {}
                    params_m = re.search(r'"(?:parameters|arguments)"\s*:\s*(\{[\s\S]*?\})', candidate_json)
                    if params_m:
                        try:
                            extracted_params = json.loads(params_m.group(1))
                        except Exception:
                            kv_matches = re.findall(r'"([A-Za-z0-9_]+)"\s*:\s*(?:"([^"]*)"|`([^`]*)`|([0-9.]+)|(true|false))', params_m.group(1))
                            for k, v1, v2, v3, v4 in kv_matches:
                                val = v1 or v2 or v3 or (v4.lower() == "true" if v4 else "")
                                extracted_params[k] = val

                    if tool_name == "execute_code":
                        code_str = str(extracted_params.get("code") or extracted_params.get("script") or "").strip()
                        python_keywords = ["import ", "def ", "class ", "print(", "=", "return ", "for ", "while ", "try:", "if "]
                        if len(code_str) > 20 and not any(kw in code_str for kw in python_keywords):
                            citations = list(set(re.findall(r"\[([^\]\n]+?\|\s*Page\s*\d+)(?:\s*\|.*?)?\]", code_str)))
                            return FinalAnswer(action="final_answer", content=code_str, citations=citations)

                    return ToolCallProposal(
                        action="tool_call",
                        tool_name=tool_name,
                        parameters=extracted_params,
                        reason=reason
                    )
                # candidate JSON was not a recognized action; fall through
            except Exception:
                pass

    # 3. Detect SLM pseudo-action tags (e.g. [action: 'final_answer'], [Action: final_answer], Action: final_answer)
    pseudo_final = re.search(
        r"\[?\s*(?:action|type)\s*[:=]\s*['\"]?final_answer['\"]?\s*\]?",
        clean_text,
        re.IGNORECASE
    )
    if pseudo_final:
        cleaned = re.sub(
            r"\[?\s*(?:action|type)\s*[:=]\s*['\"]?final_answer['\"]?\s*\]?",
            "",
            clean_text,
            flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(r"^(?:content|answer)\s*[:=]\s*", "", cleaned, flags=re.IGNORECASE).strip()
        if len(cleaned) >= 5 or not strict:
            citations = list(set(re.findall(r"\[([^\]\n]+?\|\s*Page\s*\d+)(?:\s*\|.*?)?\]", cleaned)))
            return FinalAnswer(action="final_answer", content=cleaned, citations=citations)

    pseudo_obs = re.search(
        r"\[?\s*(?:action|type)\s*[:=]\s*['\"]?(?:step_observation|observation)['\"]?\s*\]?",
        clean_text,
        re.IGNORECASE
    )
    if pseudo_obs:
        cleaned = re.sub(
            r"\[?\s*(?:action|type)\s*[:=]\s*['\"]?(?:step_observation|observation)['\"]?\s*\]?",
            "",
            clean_text,
            flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(r"^(?:content|observation)\s*[:=]\s*", "", cleaned, flags=re.IGNORECASE).strip()
        return StepObservation(action="step_observation", content=cleaned)

    # Non-strict prose fallback: require meaningful prose (not code blocks, JSON, markup, or action tokens)
    clean_stripped = clean_text.strip()
    is_simulated = clean_stripped.startswith("[SIMULATED")
    is_json_block = clean_stripped.startswith("{") or (clean_stripped.startswith("[") and clean_stripped.endswith("]") and any(c in clean_stripped for c in [":", "{", "}"]))
    if (
        not strict
        and len(clean_stripped) >= 15
        and not clean_stripped.startswith("<")
        and not is_json_block
        and not re.search(r"['\"](?:action|step_observation|tool_call)['\"]\s*:", clean_stripped, re.IGNORECASE)
        and not re.search(r":\s*['\"](?:step_observation|tool_call)['\"]", clean_stripped, re.IGNORECASE)
    ):
        citations = list(set(re.findall(r"\[([^\]\n]+?\|\s*Page\s*\d+)(?:\s*\|.*?)?\]", clean_text)))
        return FinalAnswer(content=clean_text, citations=citations)

    return None

