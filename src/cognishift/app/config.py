import os
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING, Any

# Enforce strict offline sovereign environment at process initialization time
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY", "0")

from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from cognishift.core.network.schemas import NetworkDestination

# Project root is two levels up from this file (src/cognishift/app/config.py -> project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    """Configuration settings for CogniShift."""
    project_root: Path = PROJECT_ROOT
    operating_mode: str = "local"


    ollama_base_url: str = "http://127.0.0.1:11434"
    text_model: str = "qwen2.5:7b"
    # Unified Multimodal Qwen2-VL Layer (Moondream is deprecated as primary path)
    vision_model: str = "qwen2-vl:2b"
    multimodal_profile: str = "fast"
    qwen2_vl_fast_model: str = "qwen2-vl:2b"
    qwen2_vl_deep_model: str = "qwen2-vl:7b"
    multimodal_allow_fallback: bool = False
    data_dir: Path = PROJECT_ROOT / "data"
    database_path: Path = PROJECT_ROOT / "data" / "cognishift.db"
    chroma_path: Path = PROJECT_ROOT / "data" / "chroma"
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"
    auth_store_path: Path = PROJECT_ROOT / "data" / "private" / "auth_store.json"
    cognishift_demo_mode: bool = True
    demo_session_ttl_seconds: int = 1800
    trusted_device_required: bool = True
    device_challenge_ttl_seconds: int = 120
    device_session_ttl_seconds: int = 28800
    max_upload_size_mb: int = 50
    log_level: str = "INFO"

    # Phase 4 Sandbox Configuration
    sandbox_enabled: bool = True
    sandbox_runtime: str = "docker"  # 'docker' or 'podman'
    sandbox_image: str = "cognishift/sandbox-python:3.12-v1"
    sandbox_image_digest: str = "sha256:2fd2a36859ee06c86bb687b54ebe7c50a3eb5754ac0d5a5de0aa001ac5bb4841"
    sandbox_cpu_limit: float = 1.0
    sandbox_memory_mb: int = 512
    sandbox_pid_limit: int = 64
    sandbox_default_timeout: int = 30
    sandbox_max_timeout: int = 120
    sandbox_stdout_limit: int = 65536
    sandbox_stderr_limit: int = 65536
    sandbox_max_input_files: int = 10
    sandbox_max_input_bytes: int = 10485760
    sandbox_max_output_files: int = 10
    sandbox_max_output_file_bytes: int = 10485760
    sandbox_max_output_aggregate_bytes: int = 52428800  # 50 MiB aggregate cap

    # Phase 5 Multimodal Document Ingestion, OCR & Vision Configuration
    ocr_enabled: bool = True
    ocr_engine: str = "rapidocr"  # 'rapidocr', 'tesseract', or 'simulated'
    ocr_low_confidence_threshold: float = 0.60
    ocr_normal_confidence_threshold: float = 0.75
    max_pdf_pages: int = 200
    max_input_image_dimension: int = 4096
    max_input_image_pixels: int = 16_000_000
    max_rendered_page_dimension: int = 2048
    max_rendered_page_pixels: int = 4_194_304
    max_raster_dpi: int = 150
    max_concurrent_ocr: int = 2
    max_concurrent_vision: int = 1
    max_concurrent_model_requests: int = 1
    ocr_page_timeout: int = 60
    document_processing_timeout: int = 300
    vision_max_pages_per_doc: int = 5

    # Phase 6 Network Sovereignty & Egress Observation Configuration
    static_dir: Path = PROJECT_ROOT / "src" / "cognishift" / "app" / "static"
    network_policy_mode: str = "strict"  # 'strict' or 'development'
    network_allowed_destinations: Optional[List[Any]] = None
    fastembed_offline: bool = True
    fastembed_cache_dir: Path = PROJECT_ROOT / "data" / "models" / "fastembed"
    network_audit_max_records: int = 5000
    network_audit_retention_days: int = 7

    # Phase 7 Semantic Intent Router Configuration
    semantic_router_enabled: bool = True
    semantic_router_confidence_threshold: float = 0.70
    semantic_router_margin_threshold: float = 0.10
    semantic_router_control_confidence_threshold: float = 0.75
    semantic_router_control_margin_threshold: float = 0.12
    semantic_router_max_history_turns: int = 8
    semantic_retrieval_max_distance: float = 0.78  # Squared L2 distance threshold on unit vectors (~0.61 cosine similarity)

    # Phase 8 Hybrid Multimodal RAG with ColPali Configuration
    colpali_enabled: bool = True
    enable_multimodal_vision: bool = True
    colpali_model_path: Path = PROJECT_ROOT / "data" / "models" / "colpali"
    colpali_device: str = "cuda"
    colpali_raster_dpi: int = 150
    visual_index_backend: str = "local"  # 'local' or 'qdrant'
    visual_index_path: Path = PROJECT_ROOT / "data" / "visual_index"
    hybrid_retrieval_enabled: bool = True
    hybrid_rrf_k: int = 10
    visual_retrieval_top_k: int = 3
    visual_vlm_max_pages: int = 2
    visual_verification_enabled: bool = True
    visual_page_cache_size: int = 50

    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

Settings.PROJECT_ROOT = property(lambda self: self.project_root)

settings = Settings()


# Ensure all paths are absolute relative to project root if they were loaded as relative from .env
for field in ['data_dir', 'database_path', 'chroma_path', 'upload_dir', 'auth_store_path', 'static_dir', 'fastembed_cache_dir', 'colpali_model_path', 'visual_index_path']:
    path_val = getattr(settings, field)
    if not path_val.is_absolute():
        setattr(settings, field, PROJECT_ROOT / path_val)

