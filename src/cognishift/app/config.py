import os
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING, Any
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from cognishift.core.network.schemas import NetworkDestination

# Project root is two levels up from this file (src/cognishift/app/config.py -> project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    """Configuration settings for CogniShift."""
    operating_mode: str = "local"
    ollama_base_url: str = "http://localhost:11434"
    text_model: str = "llama3.2:3b"
    vision_model: str = "moondream"
    data_dir: Path = PROJECT_ROOT / "data"
    database_path: Path = PROJECT_ROOT / "data" / "cognishift.db"
    chroma_path: Path = PROJECT_ROOT / "data" / "chroma"
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"
    auth_store_path: Path = PROJECT_ROOT / "data" / "private" / "auth_store.json"
    max_upload_size_mb: int = 50
    log_level: str = "INFO"

    # Phase 4 Sandbox Configuration
    sandbox_enabled: bool = True
    sandbox_runtime: str = "docker"  # 'docker' or 'podman'
    sandbox_image: str = "cognishift/sandbox-python:3.12-v1"
    sandbox_image_digest: str = "sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
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

    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

settings = Settings()

# Ensure all paths are absolute relative to project root if they were loaded as relative from .env
for field in ['data_dir', 'database_path', 'chroma_path', 'upload_dir', 'auth_store_path', 'static_dir', 'fastembed_cache_dir']:
    path_val = getattr(settings, field)
    if not path_val.is_absolute():
        setattr(settings, field, PROJECT_ROOT / path_val)
