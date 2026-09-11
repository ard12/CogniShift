"""
ColPali Multi-Vector Visual Embedding Providers.
Implements late-interaction token patch extraction for document images and queries.
Guarantees strict offline execution (HF_HUB_OFFLINE=1) and explicit failure/fallback.
"""
import io
import os
import hashlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import numpy as np
from PIL import Image

from cognishift.app.config import settings

logger = logging.getLogger(__name__)

# Enforce offline mode in this process
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


class VisualEmbeddingProvider(ABC):
    """Abstract Base Class for multi-vector late-interaction embedding models."""

    @abstractmethod
    def embed_page(self, image_bytes: bytes) -> np.ndarray:
        """Extracts patch-token embeddings for a document page image. Returns (N, D)."""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> np.ndarray:
        """Extracts token embeddings for a textual query. Returns (Q, D)."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if local weights and backend are available offline."""
        pass


class ColPaliLocalProvider(VisualEmbeddingProvider):
    """
    Local ColPali late-interaction model provider using Transformers/ColPali weights.
    Loads offline from settings.colpali_model_path (default data/models/colpali/).
    """

    def __init__(self, model_path: Optional[Path] = None, device: Optional[str] = None):
        self.model_path = Path(model_path or settings.colpali_model_path)
        self.device = device or getattr(settings, "colpali_device", "cpu")
        self._model = None
        self._processor = None
        self._initialized = False

    def is_available(self) -> bool:
        if not self.model_path.exists():
            return False
        # Check for model weights or config file
        has_config = (self.model_path / "config.json").exists()
        has_weights = any(self.model_path.glob("*.safetensors")) or any(self.model_path.glob("*.bin"))
        return bool(has_config and has_weights)

    def _ensure_loaded(self):
        if self._initialized:
            return
        if not self.is_available():
            raise FileNotFoundError(
                f"ColPali local weights not found at '{self.model_path}'. "
                f"Ensure offline weights are placed in {settings.colpali_model_path}."
            )

        try:
            import torch
            from transformers import AutoProcessor
            try:
                from colpali_engine.models import ColPali, ColPaliProcessor
                self._model = ColPali.from_pretrained(
                    str(self.model_path),
                    torch_dtype=torch.float32,
                    device_map=self.device,
                    local_files_only=True
                )
                self._processor = ColPaliProcessor.from_pretrained(
                    str(self.model_path),
                    local_files_only=True
                )
            except ImportError:
                from transformers import AutoModel
                self._model = AutoModel.from_pretrained(
                    str(self.model_path),
                    torch_dtype=torch.float32,
                    device_map=self.device,
                    local_files_only=True
                )
                self._processor = AutoProcessor.from_pretrained(
                    str(self.model_path),
                    local_files_only=True
                )
            self._model.eval()
            self._initialized = True
            logger.info(f"ColPali local model successfully loaded from {self.model_path} on {self.device}")
        except Exception as e:
            self._initialized = False
            raise RuntimeError(f"Failed to load local ColPali model from {self.model_path}: {e}")

    def embed_page(self, image_bytes: bytes) -> np.ndarray:
        self._ensure_loaded()
        import torch
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        with torch.no_grad():
            batch_images = self._processor.process_images([image]).to(self.device)
            image_embeddings = self._model(**batch_images)
            # image_embeddings shape: (1, N, D)
            arr = image_embeddings[0].cpu().to(torch.float32).numpy()
            return arr

    def embed_query(self, query: str) -> np.ndarray:
        self._ensure_loaded()
        import torch
        with torch.no_grad():
            batch_queries = self._processor.process_queries([query]).to(self.device)
            query_embeddings = self._model(**batch_queries)
            # query_embeddings shape: (1, Q, D)
            arr = query_embeddings[0].cpu().to(torch.float32).numpy()
            return arr


class SimulatedVisualEmbeddingProvider(VisualEmbeddingProvider):
    """
    TEST/DEV ONLY: Generates deterministic multi-vector representations for unit testing,
    pipeline integration verification, and offline benchmarks without GPU/weight dependencies.
    STRICT POLICY: Never silently substitute in production runtime.
    """

    IS_SIMULATION: bool = True

    def __init__(self, patch_tokens: int = 32, vector_dim: int = 128):
        self.patch_tokens = patch_tokens
        self.vector_dim = vector_dim

    def is_available(self) -> bool:
        return True

    def embed_page(self, image_bytes: bytes) -> np.ndarray:
        """
        Generates deterministic pseudo-features based on image hash and spatial blocks.
        Produces shape (patch_tokens, vector_dim).
        """
        digest = hashlib.sha256(image_bytes).digest()
        seed = int.from_bytes(digest[:4], "big")
        rng = np.random.RandomState(seed)

        # Base document signature
        base_features = rng.randn(self.patch_tokens, self.vector_dim).astype(np.float32)

        # Normalize rows
        norms = np.linalg.norm(base_features, axis=-1, keepdims=True)
        return base_features / np.maximum(norms, 1e-9)

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generates deterministic query tokens based on query terms.
        Produces shape (num_query_tokens, vector_dim).
        """
        tokens = query.strip().split()
        num_q = max(4, min(len(tokens) + 2, 16))

        q_hash = hashlib.sha256(query.lower().encode("utf-8")).digest()
        seed = int.from_bytes(q_hash[:4], "big")
        rng = np.random.RandomState(seed)

        query_vectors = rng.randn(num_q, self.vector_dim).astype(np.float32)
        norms = np.linalg.norm(query_vectors, axis=-1, keepdims=True)
        return query_vectors / np.maximum(norms, 1e-9)


def get_visual_embedding_provider(allow_simulation: bool = False) -> Optional[VisualEmbeddingProvider]:
    """
    Factory for obtaining the visual embedding provider.
    STRICT USER MANDATE ENFORCEMENT:
    - If ColPali weights exist, returns ColPaliLocalProvider.
    - If weights are missing:
      - In test/dev mode (allow_simulation=True), returns SimulatedVisualEmbeddingProvider.
      - In real runtime (allow_simulation=False), returns None and logs explicit warning.
        Never silently substitute simulated embeddings in production!
    """
    local_provider = ColPaliLocalProvider()

    if getattr(settings, "colpali_enabled", False):
        if local_provider.is_available():
            return local_provider
        
        if allow_simulation:
            logger.info("Using SimulatedVisualEmbeddingProvider for TEST/DEV verification.")
            return SimulatedVisualEmbeddingProvider()

        # Real runtime: explicit fallback to text RAG
        logger.warning(
            f"ColPali enabled but weights not found at '{settings.colpali_model_path}'. "
            f"Disabling visual retrieval and falling back 100% to Text RAG."
        )
        return None

    # ColPali disabled
    if allow_simulation:
        return SimulatedVisualEmbeddingProvider()
    return None
