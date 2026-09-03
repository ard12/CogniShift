"""
OCR Provider Abstraction & Local Backends.
Supports RapidOCR (ONNX Runtime, 100% offline, CPU-first) and Simulated fallback.
Strictly fails closed if local models/binaries are missing (OCRUnavailableError).
"""
from abc import ABC, abstractmethod
import asyncio
from typing import Optional, List
import logging

from cognishift.app.config import settings
from cognishift.core.document_processing.schemas import (
    OCRResult,
    OCRTextBlock,
    BoundingBox,
    OCRUnavailableError
)

logger = logging.getLogger(__name__)


class OCRProvider(ABC):
    """Abstract interface for local optical character recognition."""

    @abstractmethod
    async def extract(self, image_bytes: bytes) -> OCRResult:
        """Extract text, confidence, and bounding boxes from image bytes."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify that local OCR engine and model weights are ready."""
        ...


class RapidOCREngine(OCRProvider):
    """
    Primary local OCR engine using RapidOCR and ONNX Runtime.
    Runs 100% offline on CPU with pre-provisioned model weights.
    """
    def __init__(self):
        self._engine = None
        self._init_error = None
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
        except Exception as e:
            self._init_error = str(e)
            logger.warning(f"RapidOCR unavailable: {e}")

    async def health_check(self) -> bool:
        return self._engine is not None

    async def extract(self, image_bytes: bytes) -> OCRResult:
        if self._engine is None:
            raise OCRUnavailableError(
                f"Local RapidOCR engine is unavailable: {self._init_error or 'models not found'}. "
                f"Automatic cloud fallback is strictly prohibited."
            )

        def _run_ocr():
            # RapidOCR accepts raw bytes or ndarray
            res, _ = self._engine(image_bytes)
            return res

        try:
            raw_results = await asyncio.to_thread(_run_ocr)
        except Exception as e:
            raise OCRUnavailableError(f"RapidOCR execution failed: {e}")

        if not raw_results:
            return OCRResult(
                text="",
                confidence=1.0,
                blocks=[],
                engine="rapidocr"
            )

        blocks: List[OCRTextBlock] = []
        text_lines: List[str] = []
        conf_scores: List[float] = []

        for item in raw_results:
            # Format: [box_points, text, confidence]
            if len(item) >= 3:
                box_pts, line_text, score = item[0], str(item[1]), float(item[2])
                xs = [p[0] for p in box_pts]
                ys = [p[1] for p in box_pts]
                bbox = BoundingBox(
                    x1=min(xs),
                    y1=min(ys),
                    x2=max(xs),
                    y2=max(ys)
                )
                blocks.append(OCRTextBlock(text=line_text, confidence=score, bbox=bbox))
                text_lines.append(line_text)
                conf_scores.append(score)

        avg_conf = sum(conf_scores) / max(len(conf_scores), 1)
        full_text = "\n".join(text_lines)

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            blocks=blocks,
            engine="rapidocr"
        )


class SimulatedOCRProvider(OCRProvider):
    """
    Deterministic Simulated OCR Backend for Tier-A unit testing.
    Returns preconfigured or synthetic text without requiring ONNX models.
    """
    def __init__(self, forced_confidence: float = 0.95, forced_text: Optional[str] = None):
        self.forced_confidence = forced_confidence
        self.forced_text = forced_text

    async def health_check(self) -> bool:
        return True

    async def extract(self, image_bytes: bytes) -> OCRResult:
        text = self.forced_text or "SIMULATED_OCR_EXTRACTED_TEXT"
        bbox = BoundingBox(x1=10.0, y1=20.0, x2=200.0, y2=50.0)
        block = OCRTextBlock(text=text, confidence=self.forced_confidence, bbox=bbox)
        return OCRResult(
            text=text,
            confidence=self.forced_confidence,
            blocks=[block],
            engine="simulated"
        )


def get_ocr_provider(engine_name: Optional[str] = None) -> OCRProvider:
    """Factory to retrieve configured OCR engine."""
    target = engine_name or settings.ocr_engine
    if target == "rapidocr":
        engine = RapidOCREngine()
        return engine
    elif target == "simulated":
        return SimulatedOCRProvider()
    else:
        raise OCRUnavailableError(f"Unsupported OCR engine '{target}'. Must be 'rapidocr' or 'simulated'.")
