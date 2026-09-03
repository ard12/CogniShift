from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

class ProviderError(Exception):
    """Base exception for model provider errors."""
    pass

class ProviderConnectionError(ProviderError):
    """Raised when the provider endpoint cannot be reached."""
    pass

class ProviderTimeoutError(ProviderError):
    """Raised when inference times out."""
    pass

@dataclass
class ModelResponse:
    """Standard response from any model provider."""
    text: str
    model_name: str
    provider: str  # 'ollama', 'simulated', etc.
    tokens_used: Optional[int] = None
    is_simulated: bool = False
    success: bool = True
    error_message: Optional[str] = None

class ModelProvider(ABC):
    """Abstract interface for LLM providers. All providers must implement this."""
    
    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        context: str = "",
        model_name: Optional[str] = None
    ) -> ModelResponse:
        """Generate text from a prompt with optional system instructions and context."""
        ...
    
    @abstractmethod
    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str = "Describe this image in detail.",
        model_name: Optional[str] = None
    ) -> ModelResponse:
        """Analyze an image and return a text description."""
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and ready."""
        ...
    
    @abstractmethod
    async def model_info(self) -> dict:
        """Return information about the available models."""
        ...

def get_provider() -> ModelProvider:
    """Factory that returns the correct provider based on settings.operating_mode."""
    from cognishift.app.config import settings
    
    if settings.operating_mode == 'local':
        from cognishift.core.ollama_provider import OllamaProvider
        return OllamaProvider()
    elif settings.operating_mode == 'simulated':
        from cognishift.core.simulated_provider import SimulatedProvider
        return SimulatedProvider()
    else:
        raise ValueError(
            f"Operating mode '{settings.operating_mode}' is not supported. "
            f"Use 'local' for Ollama or 'simulated' for development."
        )
