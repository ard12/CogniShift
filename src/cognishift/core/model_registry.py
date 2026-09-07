"""Model Registry tracking local open-weight model capabilities and hardware profiles."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ModelDefinition(BaseModel):
    """Configuration and capability metadata for a local open-weight model."""
    id: str
    name: str
    display_name: str
    provider: str = "ollama"
    model_identifier: str
    capabilities: List[str] = Field(default_factory=list)
    context_window: int = 8192
    vram_requirement_mb: int = 3000
    quality_score: float = 0.85
    latency_score: float = 0.85
    supports_tools: bool = True
    supports_images: bool = False
    supports_json_schema: bool = True
    enabled: bool = True
    priority: int = 100
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Default local catalog of open-weight models (configurable at runtime without code rewrites)
DEFAULT_MODELS: Dict[str, ModelDefinition] = {
    "llama3.2:3b": ModelDefinition(
        id="llama3.2:3b",
        name="llama3.2:3b",
        display_name="Llama 3.2 3B (General SLM)",
        provider="ollama",
        model_identifier="llama3.2:3b",
        capabilities=[
            "reasoning",
            "document_analysis",
            "summarization",
            "structured_data",
            "spreadsheet_analysis"
        ],
        context_window=8192,
        vram_requirement_mb=2500,
        quality_score=0.88,
        latency_score=0.92,
        supports_tools=True,
        supports_images=False,
        supports_json_schema=True,
        enabled=True,
        priority=100
    ),
    "qwen2.5:7b": ModelDefinition(
        id="qwen2.5:7b",
        name="qwen2.5:7b",
        display_name="Qwen 2.5 7B (General SLM & Industrial Reasoning)",
        provider="ollama",
        model_identifier="qwen2.5:7b",
        capabilities=[
            "reasoning",
            "document_analysis",
            "summarization",
            "structured_data",
            "spreadsheet_analysis",
            "coding",
            "debugging"
        ],
        context_window=32768,
        vram_requirement_mb=4600,
        quality_score=0.94,
        latency_score=0.88,
        supports_tools=True,
        supports_images=False,
        supports_json_schema=True,
        enabled=True,
        priority=125
    ),
    "moondream:latest": ModelDefinition(
        id="moondream:latest",
        name="moondream:latest",
        display_name="Moondream 2 (Industrial VLM / OCR)",
        provider="ollama",
        model_identifier="moondream:latest",
        capabilities=[
            "vision",
            "ocr",
            "document_analysis"
        ],
        context_window=4096,
        vram_requirement_mb=1800,
        quality_score=0.84,
        latency_score=0.80,
        supports_tools=False,
        supports_images=True,
        supports_json_schema=False,
        enabled=True,
        priority=110
    ),
    "moondream": ModelDefinition(
        id="moondream",
        name="moondream",
        display_name="Moondream 2 (Industrial VLM / OCR - Alias)",
        provider="ollama",
        model_identifier="moondream:latest",
        capabilities=[
            "vision",
            "ocr",
            "document_analysis"
        ],
        context_window=4096,
        vram_requirement_mb=1800,
        quality_score=0.84,
        latency_score=0.80,
        supports_tools=False,
        supports_images=True,
        supports_json_schema=False,
        enabled=True,
        priority=110
    ),
    "qwen2.5-coder:7b": ModelDefinition(
        id="qwen2.5-coder:7b",
        name="qwen2.5-coder:7b",
        display_name="Qwen 2.5 Coder 7B (Autonomous Coding Engine)",
        provider="ollama",
        model_identifier="qwen2.5-coder:7b",
        capabilities=[
            "coding",
            "debugging",
            "structured_data"
        ],
        context_window=32768,
        vram_requirement_mb=5500,
        quality_score=0.96,
        latency_score=0.90,
        supports_tools=True,
        supports_images=False,
        supports_json_schema=True,
        enabled=True,
        priority=130
    ),
    "deepseek-r1:7b": ModelDefinition(
        id="deepseek-r1:7b",
        name="deepseek-r1:7b",
        display_name="DeepSeek R1 7B (Distilled Reasoning Engine)",
        provider="ollama",
        model_identifier="deepseek-r1:7b",
        capabilities=[
            "heavy_reasoning",
            "root_cause_analysis",
            "reasoning",
            "coding",
            "debugging"
        ],
        context_window=32768,
        vram_requirement_mb=4800,
        quality_score=0.96,
        latency_score=0.80,
        supports_tools=True,
        supports_images=False,
        supports_json_schema=True,
        enabled=True,
        priority=140
    ),
    "deepseek-r1:14b": ModelDefinition(
        id="deepseek-r1:14b",
        name="deepseek-r1:14b",
        display_name="DeepSeek R1 14B (Heavy Reasoning Engine)",
        provider="ollama",
        model_identifier="deepseek-r1:14b",
        capabilities=[
            "heavy_reasoning",
            "root_cause_analysis",
            "reasoning",
            "coding",
            "debugging"
        ],
        context_window=65536,
        vram_requirement_mb=14000,
        quality_score=0.98,
        latency_score=0.50,
        supports_tools=True,
        supports_images=False,
        supports_json_schema=True,
        enabled=True,
        priority=150
    )
}

_runtime_catalog: Dict[str, ModelDefinition] = dict(DEFAULT_MODELS)


def register_model(model: ModelDefinition) -> None:
    """Register or update a model in the runtime registry."""
    _runtime_catalog[model.model_identifier] = model


def normalize_model_identifier(model_identifier: str) -> str:
    """
    Normalize model identifier, resolving untagged aliases (e.g. 'moondream' -> 'moondream:latest').
    Ensures exact alignment between configured model names, Ollama tags, and registry entries.
    """
    if not model_identifier:
        return model_identifier
    clean = model_identifier.strip().lower()
    if clean == "moondream":
        return "moondream:latest"
    if clean in _runtime_catalog:
        return _runtime_catalog[clean].model_identifier
    if f"{clean}:latest" in _runtime_catalog:
        return f"{clean}:latest"
    return model_identifier


def list_models(enabled_only: bool = False) -> List[ModelDefinition]:
    """List all unique models registered in the workbench."""
    seen_ids = set()
    models = []
    for m in _runtime_catalog.values():
        if m.model_identifier not in seen_ids:
            seen_ids.add(m.model_identifier)
            models.append(m)
    if enabled_only:
        models = [m for m in models if m.enabled]
    return sorted(models, key=lambda m: m.priority, reverse=True)


def get_model(model_identifier: str) -> Optional[ModelDefinition]:
    """Retrieve metadata for a specific model with tag normalization."""
    normalized = normalize_model_identifier(model_identifier)
    return _runtime_catalog.get(normalized) or _runtime_catalog.get(model_identifier)
