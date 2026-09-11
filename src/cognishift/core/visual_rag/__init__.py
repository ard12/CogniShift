"""
Visual RAG module for CogniShift.
Provides ColPali late-interaction multi-vector representations, visual indexing,
targeted local VLM inspection, and deterministic OCR corroboration.
"""

from cognishift.core.visual_rag.schemas import (
    PageVectorMetadata,
    VisualSearchResult,
    FusedPageEvidence,
    CorroborationResult
)
from cognishift.core.visual_rag.vector_store import (
    VisualVectorStore,
    LocalMultiVectorStore,
    QdrantVisualVectorStore,
    get_visual_vector_store
)
from cognishift.core.visual_rag.embedding_provider import (
    VisualEmbeddingProvider,
    ColPaliLocalProvider,
    SimulatedVisualEmbeddingProvider,
    get_visual_embedding_provider
)
from cognishift.core.visual_rag.page_cache import (
    PageImageCache,
    get_page_image_cache,
    render_page_image_on_demand
)
from cognishift.core.visual_rag.page_verifier import (
    DeterministicPageVerifier,
    get_page_verifier
)

__all__ = [
    "PageVectorMetadata",
    "VisualSearchResult",
    "FusedPageEvidence",
    "CorroborationResult",
    "VisualVectorStore",
    "LocalMultiVectorStore",
    "QdrantVisualVectorStore",
    "get_visual_vector_store",
    "VisualEmbeddingProvider",
    "ColPaliLocalProvider",
    "SimulatedVisualEmbeddingProvider",
    "get_visual_embedding_provider",
    "PageImageCache",
    "get_page_image_cache",
    "render_page_image_on_demand",
    "DeterministicPageVerifier",
    "get_page_verifier",
]
