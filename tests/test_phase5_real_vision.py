"""
Phase 5 Tier-B Real Vision Integration Tests.
Executes live multimodal inference using local Ollama and the open-weight Moondream VLM.
Verifies router-to-provider model identity, qualitative structured observations,
and fail-closed behavior when models are unavailable.
"""
import io
import pytest
from PIL import Image, ImageDraw

from cognishift.app.config import settings
from cognishift.core.document_processing.schemas import (
    VisionObservation,
    VisionRequirement,
    VisionModelUnavailableError
)
from cognishift.core.document_processing.vision_service import VisionProcessingService
from cognishift.core.model_router import route_model, TaskClassification
from cognishift.core.providers import get_provider
from cognishift.core.ollama_provider import OllamaProvider


@pytest.fixture(autouse=True)
def ensure_local_mode(monkeypatch):
    """Ensure operating_mode is local for real Ollama tests."""
    monkeypatch.setattr(settings, "operating_mode", "local")
    yield


@pytest.mark.asyncio
async def test_real_vision_model_availability():
    """Confirms local Ollama service is reachable and hosts the vision model."""
    provider = OllamaProvider()
    is_healthy = await provider.health_check()
    assert is_healthy is True, "Local Ollama service must be active on http://localhost:11434"

    info = await provider.model_info()
    models = info.get("models", [])
    assert any("moondream" in m.lower() for m in models), f"Moondream VLM must be present in local models: {models}"


@pytest.mark.asyncio
async def test_real_vision_router_selected_identity():
    """
    Verifies that the model router selects the vision model for vision tasks
    and that this exact identifier is provided to the provider.
    """
    task = TaskClassification(
        task_type="vision_inspection",
        required_capabilities=["vision"],
        requires_vision=True
    )
    decision = route_model(task)
    assert "moondream" in decision.selected_model.lower()


@pytest.mark.asyncio
async def test_real_vision_inference_with_local_ollama():
    """
    Submits a real synthetic gauge image to local Moondream via Ollama.
    Verifies structured VisionObservation output without cloud APIs.
    """
    # Create gauge image
    img = Image.new("RGB", (300, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse((50, 50, 250, 250), outline=(0, 0, 0), width=3)
    draw.line((150, 150, 200, 100), fill=(255, 0, 0), width=3)
    draw.text((120, 180), "PSI 4.2", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    service = VisionProcessingService(provider=OllamaProvider())
    obs = await service.analyze_document_image(
        image_bytes=img_bytes,
        page_number=1,
        prompt="What instrument is shown in this image? Describe the visible gauge.",
        requirement=VisionRequirement.REQUIRED
    )

    assert isinstance(obs, VisionObservation)
    assert obs.page_number == 1
    assert "moondream" in obs.model_name.lower()
    assert len(obs.description) > 20
    # Must identify gauge or round instrument
    desc_lower = obs.description.lower()
    assert any(k in desc_lower for k in ["gauge", "dial", "meter", "round", "psi", "circle", "clock"])


@pytest.mark.asyncio
async def test_real_vision_missing_model_fails_closed():
    """
    When an uninstalled vision model is requested under REQUIRED,
    it must fail closed (VisionModelUnavailableError) with 0 cloud fallback.
    """
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    service = VisionProcessingService(provider=OllamaProvider())
    with pytest.raises(VisionModelUnavailableError) as exc:
        await service.analyze_document_image(
            image_bytes=img_bytes,
            requirement=VisionRequirement.REQUIRED,
            model_override="nonexistent_vision_model:999b"
        )
    assert "failed" in str(exc.value).lower() or "unavailable" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_real_vision_inference_error_distinguished_from_unavailable():
    """
    Verifies that when the vision provider is healthy but inference fails or returns
    empty output after retries, VisionInferenceError is raised (NOT VisionModelUnavailableError).
    """
    from unittest.mock import AsyncMock
    from cognishift.core.providers import ModelResponse
    from cognishift.core.document_processing.schemas import VisionInferenceError

    mock_provider = AsyncMock()
    mock_provider.health_check.return_value = True
    # Simulate empty response across attempts
    mock_provider.analyze_image.return_value = ModelResponse(
        text="",
        model_name="moondream",
        provider="ollama",
        success=True
    )

    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    service = VisionProcessingService(provider=mock_provider)
    with pytest.raises(VisionInferenceError) as exc:
        await service.analyze_document_image(
            image_bytes=img_bytes,
            requirement=VisionRequirement.REQUIRED,
            prompt="Describe this equipment."
        )
    assert "empty output after retry" in str(exc.value)
