"""
Schemas and data models for CogniShift Presentation Generation.
Defines typed slide specifications, themes, and layout contracts.
"""
from enum import Enum
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class SlideType(str, Enum):
    TITLE = "title"
    SECTION = "section"
    EXECUTIVE_SUMMARY = "executive_summary"
    BULLETS = "bullets"
    TWO_COLUMN = "two_column"
    EVIDENCE_SUMMARY = "evidence_summary"
    TIMELINE = "timeline"
    METRIC_KPI = "metric_kpi"
    IMAGE_WITH_EXPLANATION = "image_with_explanation"
    CHART = "chart"
    TABLE = "table"
    ROOT_CAUSE = "root_cause"
    RECOMMENDED_ACTIONS = "recommended_actions"
    SOURCE_APPENDIX = "source_appendix"


class ThemeName(str, Enum):
    EXECUTIVE = "executive"
    ENGINEERING = "engineering"
    OPERATIONS = "operations"
    GOVERNMENT_PSU = "government_psu"


class MetricCard(BaseModel):
    label: str
    value: str
    subtext: Optional[str] = None
    status: Optional[str] = None  # 'NORMAL', 'WARNING', 'CRITICAL'


class SlideSpec(BaseModel):
    """Specification for a single slide in a presentation."""
    slide_type: SlideType = SlideType.BULLETS
    title: str
    subtitle: Optional[str] = None
    body: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    left_column: Optional[Union[str, List[str]]] = None
    right_column: Optional[Union[str, List[str]]] = None
    column_left: Optional[Union[str, List[str]]] = None
    column_right: Optional[Union[str, List[str]]] = None
    timeline_items: List[Dict[str, str]] = Field(default_factory=list)
    table: Optional[Dict[str, Any]] = None  # {"headers": [...], "rows": [[...], ...]}
    metrics: List[MetricCard] = Field(default_factory=list)
    image_artifact_ids: List[Union[int, str]] = Field(default_factory=list)
    chart_artifact_ids: List[Union[int, str]] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    speaker_notes: Optional[str] = None
    footer: Optional[str] = None
    required_elements: List[str] = Field(default_factory=list)

    def get_left_column_items(self) -> List[str]:
        val = self.left_column or self.column_left or self.bullets
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [line.strip() for line in val.split("\n") if line.strip()]
        return []

    def get_right_column_items(self) -> List[str]:
        val = self.right_column or self.column_right
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [line.strip() for line in val.split("\n") if line.strip()]
        return []

    def get_all_sources(self) -> List[str]:
        all_s = []
        if self.sources:
            all_s.extend(self.sources)
        if self.source_refs:
            for s in self.source_refs:
                if s not in all_s:
                    all_s.append(s)
        return all_s


class PresentationSpec(BaseModel):
    """Full specification for a multi-slide presentation."""
    title: str
    subtitle: Optional[str] = None
    author: str = "CogniShift Sovereign Workbench"
    audience: Optional[str] = None
    theme: ThemeName = ThemeName.EXECUTIVE
    slides: List[SlideSpec] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
