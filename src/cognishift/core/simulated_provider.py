from cognishift.core.providers import ModelProvider, ModelResponse

class SimulatedProvider(ModelProvider):
    """A simulated model provider for development and testing."""
    
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        context: str = "",
        model_name: str = None
    ) -> ModelResponse:
        """Return a simulated text response."""
        short_prompt = prompt[:50]
        chosen_model = model_name or "simulated-text"
        text = (
            f"[SIMULATED RESPONSE] Based on the provided context about {short_prompt}... "
            "The system would analyze this query using the configured local model. "
            "In production, this response would come from the Ollama-hosted LLM."
        )
        return ModelResponse(
            text=text,
            model_name=chosen_model,
            provider="simulated",
            is_simulated=True
        )

    async def analyze_image(self, image_bytes: bytes, prompt: str = "Describe this image in detail.") -> ModelResponse:
        """Return a simulated image analysis response."""
        text = (
            "[SIMULATED VISION] Image analysis would be performed by the local vision model. "
            "The model would describe the contents of the uploaded image, identify equipment, "
            "warning indicators, and error codes visible in the image."
        )
        return ModelResponse(
            text=text,
            model_name="simulated-vision",
            provider="simulated",
            is_simulated=True
        )

    async def health_check(self) -> bool:
        """Always return True for the simulated provider."""
        return True

    async def model_info(self) -> dict:
        """Return fake model information for the simulated provider."""
        return {
            "provider": "simulated",
            "models": ["simulated-text", "simulated-vision"],
            "status": "simulated",
            "warning": "This provider returns fake responses for development only. Do not present simulated output as real inference."
        }
