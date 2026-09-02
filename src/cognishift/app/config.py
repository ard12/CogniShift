import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    max_upload_size_mb: int = 50
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore")

settings = Settings()

# Ensure all paths are absolute relative to project root if they were loaded as relative from .env
for field in ['data_dir', 'database_path', 'chroma_path', 'upload_dir']:
    path_val = getattr(settings, field)
    if not path_val.is_absolute():
        setattr(settings, field, PROJECT_ROOT / path_val)
