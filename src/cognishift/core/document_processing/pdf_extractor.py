"""
Native PDF Extraction & Bounded Page Rasterizer.
Extracts native text and embedded images using PyMuPDF.
Enforces 1-based human-facing page numbering and bounded rasterization.
"""
from pathlib import Path
from typing import Tuple
import pymupdf

from cognishift.app.config import settings
from cognishift.core.document_processing.schemas import (
    CorruptedDocumentError,
    ResourceLimitExceededError
)


def extract_native_page(doc: pymupdf.Document, page_number: int) -> Tuple[str, int]:
    """
    Extracts native text and image count from a 1-based page number.
    Converts 1-based page_number to 0-based PyMuPDF page index.
    """
    if page_number < 1 or page_number > len(doc):
        raise ValueError(f"Page number {page_number} out of bounds (1..{len(doc)})")
    
    page_idx = page_number - 1
    page = doc[page_idx]
    
    try:
        text = page.get_text("text") or ""
        images = page.get_images()
        image_count = len(images) if images else 0
        return text, image_count
    except Exception as e:
        raise CorruptedDocumentError(f"Error reading page {page_number}: {e}")


def render_page_to_png_bytes(doc: pymupdf.Document, page_number: int, dpi: int = 150) -> bytes:
    """
    Renders a single PDF page to PNG bytes on demand for targeted OCR.
    Enforces strict memory and dimension bounds (max 2048x2048 px).
    """
    if page_number < 1 or page_number > len(doc):
        raise ValueError(f"Page number {page_number} out of bounds (1..{len(doc)})")
    
    page_idx = page_number - 1
    page = doc[page_idx]
    
    # Calculate scale based on desired DPI (default 72 points per inch in PDF)
    scale = dpi / 72.0
    rect = page.rect
    width = rect.width * scale
    height = rect.height * scale

    # Bound rendered dimensions to max_rendered_page_dimension
    max_dim = settings.max_rendered_page_dimension
    if width > max_dim or height > max_dim:
        reduction = min(max_dim / width, max_dim / height)
        scale *= reduction

    # Verify total pixel bound
    if (rect.width * scale) * (rect.height * scale) > settings.max_rendered_page_pixels:
        raise ResourceLimitExceededError(
            f"Rendered page {page_number} exceeds maximum pixel limit of {settings.max_rendered_page_pixels}px."
        )

    mat = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    return png_bytes
