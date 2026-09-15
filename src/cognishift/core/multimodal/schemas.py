"""
Unified Multimodal Schemas for CogniShift.
Defines typed profiles (FAST / DEEP), structured visual observation contracts,
and comprehensive inference audit metadata.
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class MultimodalModelProfile(str, Enum):
    FAST = "fast"
    DEEP = "deep"


class VisualRelationItem(BaseModel):
    subject: str
    relation_type: str = "CONNECTED_TO"
    object: str
    evidence_basis: str = ""


class StructuredVisualObservation(BaseModel):
    """
    Standard machine-readable visual schema returned by both FAST and DEEP profiles.
    Strictly parsed from local VLM structured output.
    """
    observed_equipment_tags: List[str] = Field(default_factory=list)
    observed_instrument_tags: List[str] = Field(default_factory=list)
    observed_relations: List[VisualRelationItem] = Field(default_factory=list)
    numeric_claims: List[Dict[str, Any]] = Field(default_factory=list)
    visual_observations: List[str] = Field(default_factory=list)


class MultimodalModelConfig(BaseModel):
    """Configuration mapping for a profile to local model tags."""
    profile: MultimodalModelProfile
    primary_model_tag: str
    fallback_model_tag: Optional[str] = None
    allow_fallback: bool = False
    context_window: int = 4096


class MultimodalInferenceResult(BaseModel):
    """Complete execution record for a multimodal inference request."""
    requested_profile: MultimodalModelProfile
    actual_profile: MultimodalModelProfile
    requested_model: str
    resolved_model: str
    actual_model: str
    provider: str = "ollama"
    device: Optional[str] = "UNKNOWN"
    latency_ms: float = 0.0
    success: bool = False
    failure_reason: Optional[str] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    raw_text: str = ""
    structured_observation: StructuredVisualObservation = Field(default_factory=StructuredVisualObservation)
    input_image_sha256: Optional[str] = None
