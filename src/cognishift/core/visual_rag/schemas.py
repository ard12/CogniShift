"""
Schemas for Visual RAG, multi-vector representations, and evidence corroboration.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PageVectorMetadata(BaseModel):
    """Metadata describing indexed visual patch vectors for a document page or presentation slide."""
    workspace_id: int
    source_id: int
    processing_version: str
    page_number: int
    filename: str
    checksum: str
    dpi: int = 150
    width: Optional[int] = None
    height: Optional[int] = None
    vector_file_path: Optional[str] = None
    token_count: int = 0
    vector_dim: int = 128
    created_at: Optional[str] = None
    document_type: str = "pdf"
    locator_kind: str = "page"  # 'page', 'slide', 'sheet_tile', 'section'
    slide_number: Optional[int] = None


class VisualSearchResult(BaseModel):
    """Result of a late-interaction MaxSim visual search."""
    workspace_id: int
    source_id: int
    processing_version: str
    page_number: int
    filename: str
    score: float
    token_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    document_type: str = "pdf"
    locator_kind: str = "page"
    slide_number: Optional[int] = None


class CorroborationResult(BaseModel):
    """Detailed verification/corroboration of a VLM claim against OCR evidence."""
    claim_type: str  # 'numeric', 'instrument_tag', 'unit', 'reading'
    claimed_value: str
    ocr_found_value: Optional[str] = None
    corroborated: bool = False
    details: str = ""


class FusedPageEvidence(BaseModel):
    """Fused multimodal evidence record uniting text and visual retrieval channels."""
    workspace_id: int = 1
    source_id: int
    processing_version: str
    page_number: int
    filename: str
    retrieval_channel: str = "hybrid"  # 'TEXT', 'VISUAL', or 'BOTH'
    document_type: str = "pdf"
    locator_kind: str = "page"
    slide_number: Optional[int] = None
    text_score: Optional[float] = None
    text_distance: Optional[float] = None
    visual_score: Optional[float] = None
    fused_score: float = 0.0
    text_snippets: List[str] = Field(default_factory=list)
    vlm_observation: Optional[str] = None
    corroboration_results: List[CorroborationResult] = Field(default_factory=list)
    section_heading: Optional[str] = None
    ocr_corroborated: Optional[bool] = None  # None = not checked, True = corroborated, False = discrepancy
    citation: str = ""
