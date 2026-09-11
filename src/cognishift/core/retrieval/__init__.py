"""
CogniShift Modular Retrieval Subsystem.
Includes TextRetriever, VisualRetriever, EvidenceFusion, and HybridDocumentRetriever.
"""
from cognishift.core.retrieval.text_retriever import TextRetriever
from cognishift.core.retrieval.visual_retriever import VisualRetriever
from cognishift.core.retrieval.evidence_fusion import EvidenceFusion, QueryIntentWeighting
from cognishift.core.retrieval.hybrid_retriever import (
    HybridDocumentRetriever,
    get_hybrid_retriever
)

__all__ = [
    "TextRetriever",
    "VisualRetriever",
    "EvidenceFusion",
    "QueryIntentWeighting",
    "HybridDocumentRetriever",
    "get_hybrid_retriever",
]
