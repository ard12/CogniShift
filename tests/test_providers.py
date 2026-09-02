import pytest
from cognishift.core.simulated_provider import SimulatedProvider
from cognishift.core.providers import ModelResponse, get_provider

@pytest.mark.asyncio
async def test_simulated_provider_generate():
    provider = SimulatedProvider()
    response = await provider.generate_text("test prompt for generation")
    assert response.is_simulated is True
    assert response.provider == "simulated"
    assert "[SIMULATED RESPONSE]" in response.text

@pytest.mark.asyncio
async def test_simulated_provider_health():
    provider = SimulatedProvider()
    is_healthy = await provider.health_check()
    assert is_healthy is True

@pytest.mark.asyncio
async def test_simulated_provider_image():
    provider = SimulatedProvider()
    response = await provider.analyze_image(b"fake_image_bytes")
    assert response.is_simulated is True
    assert "[SIMULATED VISION]" in response.text

def test_factory_simulated_mode(monkeypatch):
    from cognishift.app.config import settings
    monkeypatch.setattr(settings, "operating_mode", "simulated")
    
    provider = get_provider()
    assert isinstance(provider, SimulatedProvider)

def test_factory_rejects_external(monkeypatch):
    from cognishift.app.config import settings
    monkeypatch.setattr(settings, "operating_mode", "external")
    
    with pytest.raises(ValueError, match="Operating mode 'external' is not supported"):
        get_provider()

def test_model_response_dataclass():
    resp = ModelResponse(
        text="Hello",
        model_name="test-model",
        provider="test-provider"
    )
    assert resp.text == "Hello"
    assert resp.model_name == "test-model"
    assert resp.provider == "test-provider"
    assert resp.is_simulated is False
    assert resp.tokens_used is None
