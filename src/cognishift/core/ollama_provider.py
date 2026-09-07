import base64
import logging
import httpx
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)
from cognishift.app.config import settings
from cognishift.core.network.client import get_sovereign_async_client
from cognishift.core.network.schemas import NetworkPolicyViolation
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
        model_name: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> ModelResponse:
        """Generate text from a prompt using the specified or default local Ollama model with optional multi-turn history."""
        target_model = model_name or self.text_model
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            for turn in history:
                if isinstance(turn, dict) and "role" in turn and "content" in turn:
                    messages.append({"role": turn["role"], "content": turn["content"]})
        
        user_content = prompt
        if context:
            user_content = f"{context}\n\n{prompt}"
            
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": 16384}
        }

        try:
            async with get_sovereign_async_client(timeout=120.0, component="ollama_provider") as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                if response.status_code != 200:
                    err_body = response.text
                    logger.error(f"Ollama /api/chat error {response.status_code}: {err_body}")
                    # If model is deepseek or chat endpoint rejected request, try /api/generate fallback
                    if "deepseek" in target_model.lower() or response.status_code == 400:
                        gen_prompt = ""
                        if system_prompt:
                            gen_prompt += f"System: {system_prompt}\n\n"
                        if context:
                            gen_prompt += f"Context:\n{context}\n\n"
                        gen_prompt += f"User: {prompt}"
                        gen_payload = {
                            "model": target_model,
                            "prompt": gen_prompt,
                            "stream": False,
                            "options": {"num_ctx": 16384}
                        }
                        logger.info(f"Attempting /api/generate fallback for {target_model}...")
                        gen_resp = await client.post(f"{self.base_url}/api/generate", json=gen_payload)
                        if gen_resp.status_code == 200:
                            gen_data = gen_resp.json()
                            return ModelResponse(
                                text=gen_data.get("response", ""),
                                model_name=target_model,
                                provider="ollama",
                                tokens_used=gen_data.get("eval_count"),
                                is_simulated=False,
                                success=True
                            )
                        else:
                            logger.error(f"Ollama /api/generate fallback also failed {gen_resp.status_code}: {gen_resp.text}")
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
        except NetworkPolicyViolation as e:
            raise ProviderError(f"Network policy violation: {e}")
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
            async with get_sovereign_async_client(timeout=120.0, component="ollama_provider") as client:
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
        except NetworkPolicyViolation as e:
            return ModelResponse(
                text=f"[VISION POLICY VIOLATION: {e}]",
                model_name=target_model,
                provider="ollama",
                is_simulated=False,
                success=False,
                error_message=str(e)
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
            async with get_sovereign_async_client(timeout=5.0, component="ollama_provider") as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, Exception):
            return False

    async def model_info(self) -> dict:
        """Return information about the available models on the local Ollama instance."""
        try:
            async with get_sovereign_async_client(timeout=5.0, component="ollama_provider") as client:
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
