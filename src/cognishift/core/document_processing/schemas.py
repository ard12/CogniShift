"""
CogniShift Phase 5 Strict Schemas and Exceptions.
Strict typed contracts for document inspection, native extraction, OCR, VLM vision, and provenance.
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------

class ExtractionMethod(str, Enum):
    NATIVE = "native"
    OCR = "ocr"
    VLM = "vlm"
    HYBRID = "hybrid"


class VisionRequirement(str, Enum):
    NOT_REQUIRED = "not_required"
    OPTIONAL = "optional"
    REQUIRED = "required"


class DocumentType(str, Enum):
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    UNSUPPORTED = "unsupported"


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------

class DocumentProcessingError(Exception):
    """Base exception for all Phase 5 document processing operations."""
    pass


class UnsupportedFileError(DocumentProcessingError):
    """Raised when file format is not supported or magic bytes do not match."""
    pass


class CorruptedDocumentError(DocumentProcessingError):
    """Raised when document parser encounters corrupted or unreadable data."""
    pass


class OCRUnavailableError(DocumentProcessingError):
    """Raised when local OCR engine or local weights/binaries are missing."""
    pass


class VisionModelUnavailableError(DocumentProcessingError):
    """Raised when required local vision model is unavailable."""
    pass


class ResourceLimitExceededError(DocumentProcessingError):
    """Raised when document exceeds page count, dimension, or byte limits."""
    pass


# -----------------------------------------------------------------------------
# OCR Models
# -----------------------------------------------------------------------------

class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class OCRTextBlock(BaseModel):
    text: str
    confidence: Optional[float] = None
    bbox: Optional[BoundingBox] = None


class OCRResult(BaseModel):
    text: str
    confidence: Optional[float] = None
    blocks: List[OCRTextBlock] = Field(default_factory=list)
    engine: str = "rapidocr"


# -----------------------------------------------------------------------------
# Vision Models
# -----------------------------------------------------------------------------

class VisionObservation(BaseModel):
    page_number: int
    description: str
    detected_equipment: List[str] = Field(default_factory=list)
    anomalies_observed: List[str] = Field(default_factory=list)
    uncertainty_notes: List[str] = Field(default_factory=list)
    model_name: str


# -----------------------------------------------------------------------------
# Document & Page Models
# -----------------------------------------------------------------------------

class ExtractedPage(BaseModel):
    page_number: int = Field(ge=1, description="Human-facing 1-based page number")
    text: str
    extraction_method: ExtractionMethod
    ocr_confidence: Optional[float] = None
    ocr_uncertain: bool = False
    needs_vision: bool = False
    has_images: bool = False
    image_count: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentInspectionResult(BaseModel):
    document_type: DocumentType
    is_valid: bool
    page_count: int = 0
    file_size_bytes: int = 0
    mime_type: str = "application/octet-stream"
    error_message: Optional[str] = None
