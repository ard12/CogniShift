"""
Bounded Image Preprocessing.
Ensures uploaded images and rendered pages conform to dimensional boundaries,
normalizes contrast, and prepares optimal inputs for local OCR and VLM.
"""
import io
from PIL import Image, ImageEnhance, ImageOps

from cognishift.app.config import settings
from cognishift.core.document_processing.schemas import (
    ResourceLimitExceededError,
    CorruptedDocumentError
)


def preprocess_image_for_ocr(image_bytes: bytes) -> bytes:
    """
    Applies bounded preprocessing for OCR text recognition:
    1. Auto-orients based on EXIF tags.
    2. Resizes if dimensions exceed MAX_RENDERED_PAGE_DIMENSION.
    3. Converts to grayscale and enhances contrast.
    Returns processed PNG bytes.
    """
    try:
        Image.MAX_IMAGE_PIXELS = settings.max_input_image_pixels
        with Image.open(io.BytesIO(image_bytes)) as img:
            # 1. Transpose based on EXIF orientation if available
            img = ImageOps.exif_transpose(img)

            # 2. Convert to RGB / Grayscale
            if img.mode != 'L':
                img = img.convert('L')

            # 3. Bound dimensions
            w, h = img.size
            max_dim = settings.max_rendered_page_dimension
            if w > max_dim or h > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            # 4. Enhance contrast slightly for text legibility
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.4)

            out_buf = io.BytesIO()
            img.save(out_buf, format="PNG")
            return out_buf.getvalue()

    except Exception as e:
        raise CorruptedDocumentError(f"Image preprocessing failed: {e}")


def prepare_image_for_vision(image_bytes: bytes) -> bytes:
    """
    Prepares an image for local VLM (Moondream/Ollama):
    Ensures RGB mode and bounds dimensions to avoid context/GPU exhaustion.
    """
    try:
        Image.MAX_IMAGE_PIXELS = settings.max_input_image_pixels
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            w, h = img.size
            max_dim = settings.max_rendered_page_dimension
            if w > max_dim or h > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=90)
            return out_buf.getvalue()

    except Exception as e:
        raise CorruptedDocumentError(f"Vision image preparation failed: {e}")
