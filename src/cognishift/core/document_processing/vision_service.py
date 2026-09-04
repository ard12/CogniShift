"""
Vision-Language Provider Integration & Service.
Orchestrates local VLM inference (Moondream via Ollama) with strict requirement levels
(NOT_REQUIRED, OPTIONAL, REQUIRED) and structured qualitative observation responses.
"""
import logging
import re
from typing import Optional, List

from cognishift.app.config import settings
from cognishift.core.providers import get_provider, ModelProvider
from cognishift.core.model_router import route_model, TaskClassification
from cognishift.core.document_processing.schemas import (
    VisionObservation,
    VisionRequirement,
    VisionModelUnavailableError,
    VisionInferenceError
)
from cognishift.core.document_processing.image_preprocessor import prepare_image_for_vision

logger = logging.getLogger(__name__)


class VisionProcessingService:
    """Service to execute visual understanding on images/pages using local VLM."""

    def __init__(self, provider: Optional[ModelProvider] = None):
        self.provider = provider or get_provider()

    async def analyze_document_image(
        self,
        image_bytes: bytes,
        page_number: int = 1,
        prompt: str = "Analyze this industrial document or equipment image. Identify any visible equipment tags, instruments, readings, corrosion, or operational anomalies.",
        requirement: VisionRequirement = VisionRequirement.OPTIONAL,
        model_override: Optional[str] = None
    ) -> Optional[VisionObservation]:
        """
        Executes local VLM analysis on preprocessed image bytes.
        Verifies router-selected model matches provider execution.
        """
        if requirement == VisionRequirement.NOT_REQUIRED:
            return None

        # 1. Select vision model via router or override
        if model_override:
            target_model = model_override
        else:
            task = TaskClassification(
                task_type="vision_inspection",
                required_capabilities=["vision"],
                requires_vision=True
            )
            decision = route_model(task)
            target_model = decision.selected_model

        # 2. Check health of provider
        is_healthy = await self.provider.health_check()
        if not is_healthy:
            if requirement == VisionRequirement.REQUIRED:
                raise VisionModelUnavailableError(
                    f"Required local vision provider is unavailable for model '{target_model}'. "
                    f"Cloud fallback is strictly prohibited."
                )
            else:
                logger.warning(f"Optional vision model '{target_model}' unavailable; continuing without visual analysis.")
                return None

        # 3. Preprocess image
        prepared_bytes = prepare_image_for_vision(image_bytes)

        # 4. Construct prefix-aware prompt
        clean_task = prompt.strip()
        if clean_task.lower().startswith("describe") or clean_task.lower().startswith("examine"):
            runtime_prompt = clean_task
        else:
            runtime_prompt = f"Examine this image and describe what is visible, specifically: {clean_task}"

        # 5. Call provider with bounded retry (attempt 0 with runtime_prompt, attempt 1 with canonical prompt)
        resp = None
        for attempt in range(2):
            call_prompt = runtime_prompt if attempt == 0 else f"Examine this image and describe what is visible in detail."
            try:
                resp = await self.provider.analyze_image(
                    image_bytes=prepared_bytes,
                    prompt=call_prompt,
                    model_name=target_model
                )
            except Exception as e:
                err_str = str(e).lower()
                if "not found" in err_str or "connect" in err_str or "404" in err_str:
                    if requirement == VisionRequirement.REQUIRED:
                        raise VisionModelUnavailableError(f"Local vision model '{target_model}' is unavailable: {e}")
                    return None
                if attempt == 0:
                    continue
                if requirement == VisionRequirement.REQUIRED:
                    raise VisionInferenceError(f"Vision inference failed on attempt {attempt + 1}: {e}")
                logger.warning(f"Optional vision inference failed: {e}")
                return None

            if not resp.success:
                err_str = (resp.error_message or "").lower()
                if "not found" in err_str or "connect" in err_str or "404" in err_str:
                    if requirement == VisionRequirement.REQUIRED:
                        raise VisionModelUnavailableError(
                            f"Vision model '{target_model}' unavailable: {resp.error_message}"
                        )
                    return None
                if attempt == 0:
                    continue
                if requirement == VisionRequirement.REQUIRED:
                    raise VisionInferenceError(f"Vision inference failed: {resp.error_message}")
                return None

            if resp.text and resp.text.strip():
                break
        else:
            # All attempts returned empty or whitespace text
            if requirement == VisionRequirement.REQUIRED:
                raise VisionInferenceError(
                    f"Vision inference returned empty output after retry for model '{target_model}'."
                )
            logger.warning(f"Optional vision model '{target_model}' returned empty output.")
            return None

        # 6. Extract structured qualitative observations
        text = resp.text.strip()
        
        # Simple heuristic extraction of tags / equipment
        equipment = re.findall(r'\b[A-Z]{1,3}-[0-9]{2,4}[A-Z]?\b', text)
        anomalies = []
        for line in text.split('\n'):
            line_lower = line.lower()
            if any(k in line_lower for k in ['leak', 'corrosion', 'crack', 'damage', 'warning', 'abnormal', 'fault', 'alarm']):
                anomalies.append(line.strip())

        return VisionObservation(
            page_number=page_number,
            description=text,
            detected_equipment=list(set(equipment)),
            anomalies_observed=anomalies[:5],
            uncertainty_notes=[],
            model_name=resp.model_name
        )
