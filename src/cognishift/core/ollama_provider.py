import base64
import httpx
from typing import Optional
from cognishift.app.config import settings
from cognishift.core.providers import (
    ModelProvider,
    ModelResponse,
    ProviderConnectionError,
    ProviderTimeoutError,
    ProviderError,
)

class OllamaProvider(ModelProvider):
    """Implementation of ModelProvider for local Ollama instances."""
    
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.text_model = settings.text_model
        self.vision_model = settings.vision_model

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        context: str = "",
        model_name: Optional[str] = None
    ) -> ModelResponse:
        """Generate text from a prompt using the specified or default local Ollama model."""
        target_model = model_name or self.text_model
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        user_content = prompt
        if context:
            user_content = f"{context}\n\n{prompt}"
            
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                text = data.get("message", {}).get("content", "")
                tokens = data.get("eval_count", None)
                return ModelResponse(
                    text=text,
                    model_name=target_model,
                    provider="ollama",
                    tokens_used=tokens,
                    is_simulated=False,
                    success=True
                )
        except httpx.ConnectError as e:
            raise ProviderConnectionError(f"Cannot connect to local Ollama server at {self.base_url}: {e}")
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(f"Inference timed out after 120s: {e}")
        except Exception as e:
            raise ProviderError(f"Ollama inference error: {e}")

    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str = "Describe this image in detail.",
        model_name: Optional[str] = None
    ) -> ModelResponse:
        """Analyze an image using the local Ollama vision model."""
        target_model = model_name or self.vision_model
        b64_img = base64.b64encode(image_bytes).decode('utf-8')
        payload = {
            "model": target_model,
            "messages": [{"role": "user", "content": prompt, "images": [b64_img]}],
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                text = data.get("message", {}).get("content", "")
                return ModelResponse(
                    text=text,
                    model_name=target_model,
                    provider="ollama",
                    is_simulated=False,
                    success=True
                )
        except (httpx.ConnectError, httpx.TimeoutException, Exception) as e:
            return ModelResponse(
                text=f"[VISION ERROR: {e}]",
                model_name=target_model,
                provider="ollama",
                is_simulated=False,
                success=False,
                error_message=str(e)
            )

    async def health_check(self) -> bool:
        """Check if the local Ollama service is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, Exception):
            return False

    async def model_info(self) -> dict:
        """Return information about the available models on the local Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "provider": "ollama",
                    "base_url": self.base_url,
                    "models": models,
                    "status": "available"
                }
        except (httpx.ConnectError, httpx.TimeoutException, Exception):
            return {
                "provider": "ollama",
                "base_url": self.base_url,
                "models": [],
                "status": "unavailable"
            }
