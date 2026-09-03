from typing import Optional
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
        """Return a simulated text response adhering to the structured AgentAction protocol."""
        chosen_model = model_name or "simulated-text"
        prompt_lower = prompt.lower()
        
        # 1. Explanatory or refusal queries must strictly return natural prose (ZERO tool calls)
        if (
            "do not run" in prompt_lower or 
            "explain how" in prompt_lower or 
            "refuse" in prompt_lower or 
            "decline" in prompt_lower or
            "do not execute" in prompt_lower
        ):
            text = (
                "[SIMULATED EXPLANATION] Explaining system operations. "
                "No physical tools or actuators are triggered for explanatory inquiries."
            )
            return ModelResponse(text=text, model_name=chosen_model, provider="simulated", is_simulated=True)

        # 2. Simulated tool calling behaviors for autonomous testing
        if "emergency_pressure_relief" in prompt_lower or "emergency pressure relief" in prompt_lower:
            text = (
                '```json\n'
                '{\n'
                '  "action": "tool_call",\n'
                '  "tool_name": "emergency_pressure_relief",\n'
                '  "parameters": {"chamber_id": "REACTOR-B", "reason": "Relieve dangerous chamber pressure exceeding threshold"},\n'
                '  "reason": "Relieve dangerous chamber pressure exceeding threshold"\n'
                '}\n'
                '```'
            )
            return ModelResponse(text=text, model_name=chosen_model, provider="simulated", is_simulated=True)

        if "check_pressure" in prompt_lower or "check pressure" in prompt_lower:
            text = (
                '```json\n'
                '{\n'
                '  "action": "tool_call",\n'
                '  "tool_name": "check_pressure",\n'
                '  "parameters": {"sensor_id": "PT-101"},\n'
                '  "reason": "Verify suction pressure telemetry"\n'
                '}\n'
                '```'
            )
            return ModelResponse(text=text, model_name=chosen_model, provider="simulated", is_simulated=True)

        if "check_temperature" in prompt_lower or "check temperature" in prompt_lower:
            text = (
                '```json\n'
                '{\n'
                '  "action": "tool_call",\n'
                '  "tool_name": "check_temperature",\n'
                '  "parameters": {"sensor_id": "TT-101"},\n'
                '  "reason": "Verify discharge temperature telemetry"\n'
                '}\n'
                '```'
            )
            return ModelResponse(text=text, model_name=chosen_model, provider="simulated", is_simulated=True)

        if "restart_component" in prompt_lower:
            text = (
                '```json\n'
                '{\n'
                '  "action": "tool_call",\n'
                '  "tool_name": "restart_component",\n'
                '  "parameters": {"component_id": "PUMP-101"},\n'
                '  "reason": "Restart stalled pump unit"\n'
                '}\n'
                '```'
            )
            return ModelResponse(text=text, model_name=chosen_model, provider="simulated", is_simulated=True)

        # 3. Default final answer synthesis
        text = (
            f"[SIMULATED RESPONSE] Task objective analyzed. "
            f"All operational parameters have been inspected and confirmed within nominal limits."
        )
        return ModelResponse(text=text, model_name=chosen_model, provider="simulated", is_simulated=True)

    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str = "Describe this image in detail.",
        model_name: Optional[str] = None
    ) -> ModelResponse:
        """Return a simulated image analysis response."""
        chosen = model_name or "simulated-vision"
        text = (
            "[SIMULATED VISION] Image analysis would be performed by the local vision model. "
            "The model would describe the contents of the uploaded image, identify equipment, "
            "warning indicators, and error codes visible in the image."
        )
        return ModelResponse(
            text=text,
            model_name=chosen,
            provider="simulated",
            is_simulated=True,
            success=True
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
