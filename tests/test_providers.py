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


@pytest.mark.asyncio
async def test_simulated_provider_with_history():
    provider = SimulatedProvider()
    response = await provider.generate_text(
        "test prompt with history",
        history=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"}
        ]
    )
    assert response.is_simulated is True
    assert "[SIMULATED RESPONSE]" in response.text


@pytest.mark.asyncio
async def test_ollama_provider_history_formatting():
    from cognishift.core.ollama_provider import OllamaProvider
    from unittest.mock import patch, MagicMock, AsyncMock

    provider = OllamaProvider()
    captured_payload = {}

    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "message": {"role": "assistant", "content": "Answer with history"},
        "eval_count": 5
    }

    async def mock_post(url, json=None, **kwargs):
        nonlocal captured_payload
        captured_payload = json
        return mock_resp

    mock_client.post = mock_post

    class MockContextManager:
        async def __aenter__(self):
            return mock_client
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    with patch("cognishift.core.ollama_provider.get_sovereign_async_client", return_value=MockContextManager()):
        res = await provider.generate_text(
            prompt="What is my name?",
            system_prompt="You are an assistant.",
            history=[
                {"role": "user", "content": "My name is John."},
                {"role": "assistant", "content": "Nice to meet you, John."}
            ]
        )
        assert res.text == "Answer with history"
        messages_sent = captured_payload.get("messages", [])
        assert any(m["role"] == "system" and m["content"] == "You are an assistant." for m in messages_sent)
        assert any(m["role"] == "user" and m["content"] == "My name is John." for m in messages_sent)
        assert any(m["role"] == "assistant" and m["content"] == "Nice to meet you, John." for m in messages_sent)
        assert any(m["role"] == "user" and m["content"] == "What is my name?" for m in messages_sent)
