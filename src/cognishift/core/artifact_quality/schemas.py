"""
Authoritative Data Models, Typing, and Contracts for CogniShift Artifact Quality V3.
Enforces semantic identity, physical quantities, time windows, and quality dimensions.
"""
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field, model_validator


class DimensionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EXECUTED = "NOT_EXECUTED"


class VisualPurpose(str, Enum):
    INCIDENT_PRESSURE_EXCURSION = "incident_pressure_excursion"
    SAFE_DEPRESSURIZATION_ENVELOPE = "safe_depressurization_envelope"
    KPI_TREND = "kpi_trend"
    DOWNTIME_BREAKDOWN = "downtime_breakdown"
    ROOT_CAUSE_RANKING = "root_cause_ranking"
    EQUIPMENT_COMPARISON = "equipment_comparison"
    PROCESS_SCHEMATIC = "process_schematic"
    GENERIC_DATA_VISUAL = "generic_data_visual"


class PhysicalDimension(str, Enum):
    PRESSURE = "PRESSURE"
    TEMPERATURE = "TEMPERATURE"
    TIME = "TIME"
    FLOW = "FLOW"
    LENGTH = "LENGTH"
    VIBRATION = "VIBRATION"
    PERCENTAGE = "PERCENTAGE"
    DIMENSIONLESS = "DIMENSIONLESS"


class MeasuredQuantity(BaseModel):
    """
    Physical quantity with explicit unit, dimension, and tolerance.
    Prevents meaningless raw-number comparisons and cross-dimension confusion.
    """
    value: float
    unit: str
    dimension: PhysicalDimension
    tolerance: float = 0.02  # 2% default relative tolerance
    label: Optional[str] = None
    source_evidence_ids: List[str] = Field(default_factory=list)

    def normalize(self) -> Tuple[float, str]:
        """
        Normalizes quantity to canonical SI/engineering base units:
        - PRESSURE -> bar
        - TEMPERATURE -> degC
        - TIME -> seconds
        - FLOW -> kg/h
        - LENGTH -> mm
        - PERCENTAGE -> %
        """
        u = self.unit.strip().lower()
        d = self.dimension

        if d == PhysicalDimension.PRESSURE:
            # Canonical: bar (barg treated on gauge scale)
            if u in ("bar", "barg"):
                return self.value, "bar"
            elif u in ("kpa", "kpag"):
                return self.value / 100.0, "bar"
            elif u in ("mpa", "mpag"):
                return self.value * 10.0, "bar"
            elif u in ("psi", "psig"):
                return self.value * 0.0689476, "bar"
            elif u in ("atm",):
                return self.value * 1.01325, "bar"
            else:
                return self.value, u

        elif d == PhysicalDimension.TEMPERATURE:
            # Canonical: degC
            if u in ("degc", "c", "celsius"):
                return self.value, "degC"
            elif u in ("degf", "f", "fahrenheit"):
                return (self.value - 32.0) * 5.0 / 9.0, "degC"
            elif u in ("k", "kelvin"):
                return self.value - 273.15, "degC"
            else:
                return self.value, u

        elif d == PhysicalDimension.TIME:
            # Canonical: seconds
            if u in ("s", "sec", "seconds"):
                return self.value, "s"
            elif u in ("min", "minute", "minutes"):
                return self.value * 60.0, "s"
            elif u in ("h", "hr", "hours"):
                return self.value * 3600.0, "s"
            elif u in ("d", "days"):
                return self.value * 86400.0, "s"
            else:
                return self.value, u

        elif d == PhysicalDimension.FLOW:
            # Canonical: kg/h
            if u in ("kg/h", "kgh", "kg_h"):
                return self.value, "kg/h"
            elif u in ("t/h", "th", "tonne/h"):
                return self.value * 1000.0, "kg/h"
            elif u in ("kg/s", "kgs"):
                return self.value * 3600.0, "kg/h"
            else:
                return self.value, u

        elif d == PhysicalDimension.LENGTH:
            # Canonical: mm
            if u in ("mm", "millimeter"):
                return self.value, "mm"
            elif u in ("m", "meter"):
                return self.value * 1000.0, "mm"
            elif u in ("in", "inch", "inches"):
                return self.value * 25.4, "mm"
            else:
                return self.value, u

        elif d == PhysicalDimension.PERCENTAGE:
            if u in ("%", "pct", "percent"):
                return self.value, "%"
            elif u in ("fraction", "ratio"):
                return self.value * 100.0, "%"
            else:
                return self.value, u

        return self.value, u

    def is_compatible_with(self, other: "MeasuredQuantity", custom_tol: Optional[float] = None) -> Tuple[bool, str]:
        """
        Determines if two physical quantities match within allowable tolerance.
        Fails if physical dimensions mismatch.
        """
        if self.dimension != other.dimension:
            return False, f"Physical dimension mismatch: {self.dimension.value} vs {other.dimension.value}"

        norm_self_val, norm_self_u = self.normalize()
        norm_other_val, norm_other_u = other.normalize()

        if norm_self_u != norm_other_u:
            return False, f"Unit conversion unavailable between {self.unit} and {other.unit}"

        tol = custom_tol if custom_tol is not None else max(self.tolerance, other.tolerance)
        abs_diff = abs(norm_self_val - norm_other_val)
        base = max(abs(norm_self_val), abs(norm_other_val), 1e-6)
        rel_diff = abs_diff / base

        if rel_diff <= tol:
            return True, f"Match within tolerance ({rel_diff:.2%} <= {tol:.2%})"
        return False, f"Value mismatch: {self.value} {self.unit} ({norm_self_val:.2f} {norm_self_u}) vs {other.value} {other.unit} ({norm_other_val:.2f} {norm_other_u})"


class TimeWindow(BaseModel):
    """
    Timezone-aware time interval with deterministic set-relation algebra.
    Rejects naive datetime strings and verifies start <= end.
    """
    start: datetime
    end: datetime
    timezone_name: str = "UTC"

    @model_validator(mode="after")
    def validate_time_window(self):
        if self.start.tzinfo is None:
            self.start = self.start.replace(tzinfo=timezone.utc)
        if self.end.tzinfo is None:
            self.end = self.end.replace(tzinfo=timezone.utc)
        if self.start > self.end:
            raise ValueError(f"TimeWindow start ({self.start}) must precede end ({self.end}).")
        return self

    def to_utc(self) -> Tuple[datetime, datetime]:
        return self.start.astimezone(timezone.utc), self.end.astimezone(timezone.utc)

    def relation_to(self, other: "TimeWindow") -> str:
        """
        Computes temporal relation:
        - 'identical': exact match
        - 'contained': self inside other or other inside self
        - 'overlapping': partial intersection
        - 'disjoint': zero intersection
        """
        s1, e1 = self.to_utc()
        s2, e2 = other.to_utc()

        if s1 == s2 and e1 == e2:
            return "identical"
        if s1 >= s2 and e1 <= e2:
            return "contained"
        if s2 >= s1 and e2 <= e1:
            return "contained"
        if e1 < s2 or e2 < s1:
            return "disjoint"
        return "overlapping"


class EvidenceReference(BaseModel):
    """
    Typed citation reference binding directly to an authoritative knowledge chunk.
    Prevents unaligned parallel arrays of source IDs and checksums.
    """
    source_id: Union[int, str]
    workspace_id: int
    processing_version: str = "v1"
    checksum: str
    locator: str = ""  # e.g., "Page 2", "Rows 1-30", "Section: 3.1"
    evidence_id: str = ""
    evidence_role: str = ""  # e.g., "telemetry_basis", "design_standard", "inspection_record"
    channel: str = ""  # "pdf", "docx", "xlsx", "pptx"


class StandardClaim(BaseModel):
    """
    Verifiable engineering / regulatory standard claim.
    Claims without verified evidence fail closed.
    """
    claim_id: str
    claim_text: str
    standard_designation: str  # e.g., "ASME Section VIII Div 1", "API 521", "PESO"
    supporting_evidence_ids: List[str]
    locators: List[str] = Field(default_factory=list)
    support_status: str = "VERIFIED"  # "VERIFIED", "UNVERIFIED", "REFUTED"


class ArtifactLifecycleState(str, Enum):
    STAGING = "STAGING"
    QA_FAILED = "QA_FAILED"
    ACCEPTED = "ACCEPTED"


class ArtifactSemanticMetadata(BaseModel):
    """
    Authoritative semantic identity of an artifact visual or deliverable.
    Universal identity fields are mandatory; domain-specific fields are optional.
    """
    # Universal Identity
    artifact_type: str  # "png", "pdf", "docx", "pptx", "xlsx", "csv"
    workspace_id: int
    content_context_id: str
    source_references: List[EvidenceReference] = Field(default_factory=list)
    generation_parameters: Dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "artifact-quality-v3"

    # Optional Domain Metadata (Authority-Backed)
    artifact_id: Optional[int] = None
    scenario_id: Optional[str] = None
    subject_assets: List[str] = Field(default_factory=list)
    measurement_tags: List[str] = Field(default_factory=list)
    metric: Optional[str] = None
    units: Optional[str] = None
    chart_purpose: Optional[VisualPurpose] = None
    headline_metric: Optional[MeasuredQuantity] = None
    time_window: Optional[TimeWindow] = None
    is_synthetic_demo: bool = False


class GroundedArtifactContext(BaseModel):
    """
    Common authoritative scenario facts shared across all artifact planners.
    Prevents separate deliverables from independently hallucinating facts.
    """
    content_context_id: str
    title: str
    workspace_id: int
    scenario_id: Optional[str] = None
    subject_assets: List[str] = Field(default_factory=list)
    sensor_tags: List[str] = Field(default_factory=list)
    quantities: Dict[str, MeasuredQuantity] = Field(default_factory=dict)
    time_window: Optional[TimeWindow] = None
    claims_ledger: List[StandardClaim] = Field(default_factory=list)
    timeline_events: List[Dict[str, str]] = Field(default_factory=list)
    source_references: List[EvidenceReference] = Field(default_factory=list)
    is_synthetic_demo: bool = False
    sovereignty_statement: str = "Local sovereign execution with no public-cloud AI/model dependency in the demonstrated workflow."
    schema_version: str = "artifact-quality-v3"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CalloutType(str, Enum):
    DANGER = "DANGER"
    WARNING = "WARNING"
    CAUTION = "CAUTION"
    NOTE = "NOTE"


class CalloutBlock(BaseModel):
    """
    Structured procedural safety callout.
    Rendered with semantic border/fill styling.
    """
    callout_type: CalloutType
    title: Optional[str] = None
    text: str
    grounding_evidence_id: Optional[str] = None


class DocumentType(str, Enum):
    TECHNICAL_REPORT = "technical_report"
    SOP = "sop"
    EXECUTIVE_BRIEF = "executive_brief"
    INCIDENT_REPORT = "incident_report"
    ENGINEERING_CALCULATION = "engineering_calculation"
    MAINTENANCE_PROCEDURE = "maintenance_procedure"
    SOURCE_REGISTER = "source_register"


class QualityDimensionReport(BaseModel):
    """Detailed evaluation record for a single quality dimension."""
    dimension_name: str
    status: DimensionStatus
    severity: str = "CRITICAL"  # "CRITICAL" or "ADVISORY"
    message: str = ""
    repair_suggestion: Optional[str] = None


class QualityReport(BaseModel):
    """
    Cryptographically tied audit record of complete artifact quality evaluation.
    Persisted alongside every registered workspace artifact.
    """
    quality_report_id: str
    artifact_type: str
    content_context_id: str
    workspace_id: int
    artifact_sha256: str
    artifact_version: int = 1
    parent_artifact_sha256: Optional[str] = None
    lifecycle_state: ArtifactLifecycleState = ArtifactLifecycleState.STAGING
    demo_ready: bool = False
    enterprise_ready: bool = False
    dimensions: Dict[str, QualityDimensionReport] = Field(default_factory=dict)
    repair_attempts: int = 0
    repair_history: List[Dict[str, Any]] = Field(default_factory=list)
    visual_qa_results: List[Dict[str, Any]] = Field(default_factory=list)
    schema_version: str = "artifact-quality-v3"
    validator_versions: Dict[str, str] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def get_dimension_status(self, dim_name: str) -> DimensionStatus:
        if dim_name in self.dimensions:
            return self.dimensions[dim_name].status
        return DimensionStatus.NOT_APPLICABLE

    def get_failure_summary(self) -> str:
        failures = [
            f"{name}: {dim.message}"
            for name, dim in self.dimensions.items()
            if dim.status == DimensionStatus.FAIL
        ]
        return "; ".join(failures) if failures else "All evaluated dimensions passed."
