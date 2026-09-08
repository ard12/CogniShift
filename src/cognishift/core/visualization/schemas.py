"""
Visualization Pipeline Schemas and Contracts for CogniShift.
Enforces deterministic artifact detection and strict data contracts.
"""
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    SCATTER = "scatter"
    PIE = "pie"
    AUTO = "auto"


class ArtifactRequestContract(BaseModel):
    """
    Deterministic contract representing exact user-requested deliverables.
    Extracted via authoritative rule engine, bypassing LLM guesswork.
    """
    pdf_required: bool = False
    docx_required: bool = False
    xlsx_required: bool = False
    png_required: bool = False
    png_count: int = 0
    requested_chart_type: ChartType = ChartType.AUTO
    explicit_sheet: Optional[str] = None
    explicit_metrics: List[str] = Field(default_factory=list)
    explicit_dimensions: List[str] = Field(default_factory=list)
    is_deliverable_request: bool = False

    @property
    def total_artifacts_expected(self) -> int:
        count = 0
        if self.pdf_required:
            count += 1
        if self.docx_required:
            count += 1
        if self.xlsx_required:
            count += 1
        count += self.png_count
        return count

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class VisualizationSpec(BaseModel):
    """
    Ground-truth visualization specification.
    Contains strictly extracted numeric series and provenanced coordinates.
    Never contains hallucinated LLM values.
    """
    title: str
    source_file: str
    source_sheet: Optional[str] = None
    chart_type: ChartType
    x_column: str
    y_columns: List[str]
    x_values: List[Any]
    series: Dict[str, List[float]]
    x_label: str
    y_label: str
    output_filename: str
    provenance: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class VisualizationResult(BaseModel):
    """Execution and validation outcome for a visualization artifact."""
    success: bool
    artifact_id: Optional[int] = None
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size: int = 0
    error: Optional[str] = None
    spec: Optional[VisualizationSpec] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
