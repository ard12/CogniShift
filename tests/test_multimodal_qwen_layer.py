"""
Comprehensive Unit Tests for Unified Multimodal Qwen2-VL Layer.
Verifies FAST/DEEP profile routing, structured contract parsing,
fail-closed behavior on missing local models, fallback tracking, and telemetry.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from cognishift.core.multimodal.schemas import (
    MultimodalModelProfile,
    MultimodalInferenceResult,
    StructuredVisualObservation,
    VisualRelationItem
)
from cognishift.core.multimodal.router import MultimodalModelRouter
from cognishift.core.providers import ModelResponse


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.analyze_image = AsyncMock()
    return provider


@pytest.fixture
def dummy_image_bytes():
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"


@pytest.mark.asyncio
async def test_fast_profile_routes_to_2b(mock_provider, dummy_image_bytes):
    """Verify FAST profile resolves to configured 2B model and captures structured output."""
    router = MultimodalModelRouter(provider=mock_provider)

    mock_provider.analyze_image.return_value = ModelResponse(
        text='''```json
{
  "observed_equipment_tags": ["P-101A", "HEX-102"],
  "observed_instrument_tags": ["PT-101", "FV-302"],
  "observed_relations": [
    {
      "subject": "P-101A",
      "relation_type": "UPSTREAM_OF",
      "object": "HEX-102",
      "evidence_basis": "Process line with flow arrow"
    }
  ],
  "numeric_claims": [
    {"item": "Suction Pressure", "value": "2.4", "unit": "bar"}
  ],
  "visual_observations": ["Pump P-101A discharge feeds into HEX-102."]
}
```''',
        model_name="qwen2-vl:2b",
        provider="ollama",
        success=True
    )

    with patch.object(router, "get_local_inventory", AsyncMock(return_value=["qwen2-vl:2b", "qwen2-vl:7b"])):
        res = await router.inspect_image(
            image_bytes=dummy_image_bytes,
            profile=MultimodalModelProfile.FAST,
            task_query="Inspect pump line"
        )

        assert res.success is True
        assert res.requested_profile == MultimodalModelProfile.FAST
        assert res.actual_profile == MultimodalModelProfile.FAST
        assert res.actual_model == "qwen2-vl:2b"
        assert res.fallback_used is False
        assert "P-101A" in res.structured_observation.observed_equipment_tags
        assert "HEX-102" in res.structured_observation.observed_equipment_tags
        assert "PT-101" in res.structured_observation.observed_instrument_tags
        assert len(res.structured_observation.observed_relations) == 1
        rel = res.structured_observation.observed_relations[0]
        assert rel.subject == "P-101A"
        assert rel.relation_type == "UPSTREAM_OF"
        assert rel.object == "HEX-102"
        assert res.latency_ms > 0
        assert res.input_image_sha256 is not None


@pytest.mark.asyncio
async def test_deep_profile_routes_to_7b(mock_provider, dummy_image_bytes):
    """Verify DEEP profile resolves to configured 7B model with same schema contract."""
    router = MultimodalModelRouter(provider=mock_provider)

    mock_provider.analyze_image.return_value = ModelResponse(
        text='''{
  "observed_equipment_tags": ["R-301"],
  "observed_instrument_tags": ["TT-301"],
  "observed_relations": [],
  "numeric_claims": [],
  "visual_observations": ["Reactor R-301 vessel visible."]
}''',
        model_name="qwen2-vl:7b",
        provider="ollama",
        success=True
    )

    with patch.object(router, "get_local_inventory", AsyncMock(return_value=["qwen2-vl:2b", "qwen2-vl:7b"])):
        res = await router.inspect_image(
            image_bytes=dummy_image_bytes,
            profile=MultimodalModelProfile.DEEP,
            task_query="Examine reactor vessel"
        )

        assert res.success is True
        assert res.requested_profile == MultimodalModelProfile.DEEP
        assert res.actual_profile == MultimodalModelProfile.DEEP
        assert res.actual_model == "qwen2-vl:7b"
        assert "R-301" in res.structured_observation.observed_equipment_tags


@pytest.mark.asyncio
async def test_missing_model_fails_closed(mock_provider, dummy_image_bytes):
    """Verify missing model returns explicit MODEL_UNAVAILABLE without downloading."""
    router = MultimodalModelRouter(provider=mock_provider)

    # Local inventory only contains other models, neither 2B nor 7B
    with patch.object(router, "get_local_inventory", AsyncMock(return_value=["qwen2.5:7b", "llama3.2:3b"])):
        res = await router.inspect_image(
            image_bytes=dummy_image_bytes,
            profile=MultimodalModelProfile.FAST
        )

        assert res.success is False
        assert "MODEL_UNAVAILABLE" in res.failure_reason
        assert res.actual_model == "NONE"
        mock_provider.analyze_image.assert_not_called()


@pytest.mark.asyncio
async def test_fallback_when_configured(mock_provider, dummy_image_bytes):
    """Verify fallback executes and records provenance when allow_fallback is enabled."""
    router = MultimodalModelRouter(provider=mock_provider)

    mock_provider.analyze_image.return_value = ModelResponse(
        text='{"observed_equipment_tags": ["P-101A"], "observed_relations": []}',
        model_name="qwen2-vl:2b",
        provider="ollama",
        success=True
    )

    with patch("cognishift.core.multimodal.router.settings") as mock_settings:
        mock_settings.qwen2_vl_deep_model = "qwen2-vl:7b"
        mock_settings.qwen2_vl_fast_model = "qwen2-vl:2b"
        mock_settings.multimodal_allow_fallback = True
        mock_settings.multimodal_profile = "deep"

        # Inventory has 2B but NOT 7B
        with patch.object(router, "get_local_inventory", AsyncMock(return_value=["qwen2-vl:2b"])):
            res = await router.inspect_image(
                image_bytes=dummy_image_bytes,
                profile=MultimodalModelProfile.DEEP
            )

            assert res.success is True
            assert res.requested_profile == MultimodalModelProfile.DEEP
            assert res.actual_profile == MultimodalModelProfile.FAST
            assert res.actual_model == "qwen2-vl:2b"
            assert res.fallback_used is True
            assert "not installed" in res.fallback_reason


@pytest.mark.asyncio
async def test_malformed_json_fails_closed(mock_provider, dummy_image_bytes):
    """Verify non-JSON or malformed prose output does not manufacture typed relations."""
    router = MultimodalModelRouter(provider=mock_provider)

    mock_provider.analyze_image.return_value = ModelResponse(
        text="The image clearly shows FV-302 upstream of R-301 and pressure is high.",
        model_name="qwen2-vl:2b",
        provider="ollama",
        success=True
    )

    with patch.object(router, "get_local_inventory", AsyncMock(return_value=["qwen2-vl:2b"])):
        res = await router.inspect_image(
            image_bytes=dummy_image_bytes,
            profile=MultimodalModelProfile.FAST,
            task_query="Is FV-302 upstream of R-301?"
        )

        assert res.success is True
        assert res.failure_reason == "MALFORMED_STRUCTURED_OUTPUT"
        assert res.raw_text == "The image clearly shows FV-302 upstream of R-301 and pressure is high."
        # No relation manufactured from prose!
        assert len(res.structured_observation.observed_relations) == 0
        assert len(res.structured_observation.observed_equipment_tags) == 0


def test_prompt_separates_task_from_contract():
    """Verify inference prompt isolates user query from structured JSON contract."""
    router = MultimodalModelRouter()
    prompt = router.build_inference_prompt("What does the suction line show?")
    assert "[TASK INSTRUCTION]" in prompt
    assert "What does the suction line show?" in prompt
    assert "[STRUCTURED OUTPUT CONTRACT]" in prompt
    assert "observed_equipment_tags" in prompt
    assert "Do not infer direction or equipment presence from the task instruction" in prompt
