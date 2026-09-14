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
    Local ColPali / ColModernVBERT late-interaction model provider.
    Supports ONNX Runtime late-interaction models via FastEmbed as well as PyTorch Transformers.
    Loads locally from settings.colpali_model_path (default data/models/colpali/) with no public-cloud dependency.
    """
    IS_SIMULATION: bool = False

    def __init__(self, model_path: Optional[Path] = None, device: Optional[str] = None):
        self.model_path = Path(model_path or settings.colpali_model_path)
        self.device = device or getattr(settings, "colpali_device", "cpu")
        self._backend: str = "unknown"
        self._model = None
        self._processor = None
        self._model_name: str = "Qdrant/colmodernvbert"
        self._initialized = False
        self._query_cache: Dict[str, np.ndarray] = {}
        self.enable_query_cache: bool = True

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        if self.model_path.exists():
            if (self.model_path / "model.onnx").exists():
                return True
            if (self.model_path / "models--Qdrant--colmodernvbert").exists():
                return True
            if any(self.model_path.glob("*.safetensors")) or any(self.model_path.glob("*.bin")):
                return (self.model_path / "config.json").exists()
        
        # Check fastembed model directory
        fastembed_dir = Path("data/models/fastembed/models--Qdrant--colmodernvbert")
        if fastembed_dir.exists():
            return True
        return False

    def _ensure_loaded(self):
        if self._initialized:
            return
        if not self.is_available():
            raise FileNotFoundError(
                f"ColPali local weights not found at '{self.model_path}'. "
                f"Ensure offline weights are placed in {settings.colpali_model_path}."
            )

        # Check for ONNX model first (high-performance GPU / CPU)
        # Register CUDA and cuDNN 9 paths if present on Windows
        cuda_dirs = [
            Path(r"C:\Program Files\NVIDIA\CUDNN\v9.22\bin\12.9\x64"),
            Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin"),
        ]
        for cd in cuda_dirs:
            if cd.exists():
                try:
                    os.add_dll_directory(str(cd))
                except Exception:
                    pass
                if str(cd) not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = f"{str(cd)};{os.environ.get('PATH', '')}"

        onnx_cache_candidates = [
            self.model_path,
            Path("data/models/colpali"),
            Path("data/models/fastembed"),
            Path("data/models"),
        ]

        import onnxruntime as ort
        available_providers = ort.get_available_providers()
        if self.device in ("cuda", "gpu") or ("CUDAExecutionProvider" in available_providers and self.device != "cpu"):
            cuda_opts = {
                "device_id": 0,
                "arena_extend_strategy": "kNextPowerOfTwo",
            }
            providers = [("CUDAExecutionProvider", cuda_opts), "CPUExecutionProvider"]
        else:
            providers = ["CPUExecutionProvider"]

        for cache_dir in onnx_cache_candidates:
            if not cache_dir.exists():
                continue
            if (cache_dir / "models--Qdrant--colmodernvbert").exists() or (cache_dir / "model.onnx").exists():
                try:
                    from fastembed.late_interaction_multimodal.late_interaction_multimodal_embedding import LateInteractionMultimodalEmbedding
                    effective_cache = cache_dir if (cache_dir / "models--Qdrant--colmodernvbert").exists() else cache_dir.parent
                    self._model = LateInteractionMultimodalEmbedding(
                        "Qdrant/colmodernvbert",
                        cache_dir=str(effective_cache),
                        local_files_only=True,
                        providers=providers,
                    )
                    self._backend = "onnx_fastembed"
                    has_cuda = any((p == "CUDAExecutionProvider" or (isinstance(p, tuple) and p[0] == "CUDAExecutionProvider")) for p in providers)
                    active_prov = "CUDA" if has_cuda and "CUDAExecutionProvider" in available_providers else "CPU"
                    self._model_name = f"Qdrant/colmodernvbert (ONNX Late-Interaction on {active_prov})"
                    self._initialized = True
                    logger.info(f"ColPali/ColModernVBERT local ONNX model loaded offline on {active_prov} from {effective_cache}")
                    return
                except Exception as e:
                    logger.debug(f"Failed loading ONNX model from {cache_dir}: {e}")

        # Fallback to PyTorch / Transformers if safetensors or bin files are present
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
            self._backend = "transformers"
            self._model_name = "ColPali-PyTorch"
            self._initialized = True
            logger.info(f"ColPali local model successfully loaded from {self.model_path} on {self.device}")
        except Exception as e:
            self._initialized = False
            raise RuntimeError(f"Failed to load local ColPali model from {self.model_path}: {e}")

    def embed_page(self, image_bytes: bytes) -> np.ndarray:
        self._ensure_loaded()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if self._backend == "onnx_fastembed":
            vecs = list(self._model.embed_image([image]))[0]
            return np.asarray(vecs, dtype=np.float32)

        import torch
        with torch.no_grad():
            batch_images = self._processor.process_images([image]).to(self.device)
            image_embeddings = self._model(**batch_images)
            # image_embeddings shape: (1, N, D)
            arr = image_embeddings[0].cpu().to(torch.float32).numpy()
            return arr

    def clear_query_cache(self):
        """Clears the in-memory query embedding cache."""
        self._query_cache.clear()

    def embed_query(self, query: str, use_cache: Optional[bool] = None) -> np.ndarray:
        self._ensure_loaded()
        should_cache = self.enable_query_cache if use_cache is None else use_cache
        if should_cache and query in self._query_cache:
            return self._query_cache[query]

        if self._backend == "onnx_fastembed":
            mod = self._model.model
            encoded = mod.tokenize([query])
            input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
            # Use 1 dummy image instead of seq_length dummy images (avoids massive VRAM waste)
            pix = np.zeros((1, 1, 3, mod.image_size, mod.image_size), dtype=np.float32)
            onnx_input = {"input_ids": input_ids, "attention_mask": attention_mask, "pixel_values": pix}
            model_output = mod.model.run(mod.ONNX_OUTPUT_NAMES, onnx_input)
            from fastembed.late_interaction_multimodal.onnx_multimodal_model import OnnxOutputContext
            ctx = OnnxOutputContext(model_output=model_output[0], attention_mask=attention_mask, input_ids=input_ids)
            arr = np.asarray(list(mod._post_process_onnx_text_output(ctx))[0], dtype=np.float32)
        else:
            import torch
            with torch.no_grad():
                batch_queries = self._processor.process_queries([query]).to(self.device)
                query_embeddings = self._model(**batch_queries)
                arr = query_embeddings[0].cpu().to(torch.float32).numpy()

        if should_cache:
            self._query_cache[query] = arr
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


_cached_local_provider: Optional[ColPaliLocalProvider] = None


def get_visual_embedding_provider(allow_simulation: bool = False) -> Optional[VisualEmbeddingProvider]:
    """
    Factory for obtaining the visual embedding provider.
    STRICT USER MANDATE ENFORCEMENT:
    - If ColPali weights exist, returns cached ColPaliLocalProvider singleton.
    - If weights are missing:
      - In test/dev mode (allow_simulation=True), returns SimulatedVisualEmbeddingProvider.
      - In real runtime (allow_simulation=False), returns None and logs explicit warning.
        Never silently substitute simulated embeddings in production!
    """
    global _cached_local_provider
    if _cached_local_provider is None:
        _cached_local_provider = ColPaliLocalProvider()

    if getattr(settings, "colpali_enabled", False):
        if _cached_local_provider.is_available():
            return _cached_local_provider
        
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
