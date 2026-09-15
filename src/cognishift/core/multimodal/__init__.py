"""
Unified Multimodal Layer for CogniShift.
Provides typed profiles (FAST / DEEP), model routing, and structured visual observation schemas.
"""
from cognishift.core.multimodal.schemas import (
    MultimodalModelProfile,
    MultimodalModelConfig,
    MultimodalInferenceResult,
    StructuredVisualObservation,
    VisualRelationItem
)
from cognishift.core.multimodal.router import (
    MultimodalModelRouter,
    get_multimodal_router
)

__all__ = [
    "MultimodalModelProfile",
    "MultimodalModelConfig",
    "MultimodalInferenceResult",
    "StructuredVisualObservation",
    "VisualRelationItem",
    "MultimodalModelRouter",
    "get_multimodal_router"
]
