"""
Unit and integration tests for VisualEvidenceInspector:
- Targeted VLM observation generation
- OCR corroboration linking
- Integration with RCAEvidenceAcquirer replacing placeholder MaxSim text
- Graceful degradation when rasterization is unavailable
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from cognishift.core.retrieval.visual_inspector import (
    VisualEvidenceInspector,
    VisualInspectionResult
)
from cognishift.core.visual_rag.schemas import CorroborationResult, VisualSearchResult
from cognishift.core.rca.evidence_acquisition import RCAEvidenceAcquirer
from cognishift.core.rca.schemas import EvidenceRole, RCAEvidenceBundle


@pytest.mark.asyncio
async def test_visual_evidence_inspector_observation_extraction():
    """Verify that VisualEvidenceInspector extracts VLM observations and equipment tags."""
    mock_vision = AsyncMock()
    mock_obs = MagicMock()
    mock_obs.description = "FV-302 is drawn inline on 10-HC-301 line directly upstream of reactor R-301. Suction PT-101 reads 14.2 bar."
    mock_vision.analyze_document_image.return_value = mock_obs

    mock_verifier = AsyncMock()
    mock_corr = CorroborationResult(
        claim_type="instrument_tag",
        claimed_value="FV-302",
        ocr_found_value="FV-302",
        corroborated=True,
        details="Found in OCR tokens"
    )
    mock_verifier.verify_page_claims.return_value = [mock_corr]

    inspector = VisualEvidenceInspector(vision_service=mock_vision, verifier=mock_verifier)

    fake_path = Path("fake_drawing.pdf")
    with patch.object(inspector, "_resolve_file_path", return_value=fake_path), \
         patch("cognishift.core.retrieval.visual_inspector.render_page_image_on_demand", return_value=b"fake_png_data"), \
         patch("pathlib.Path.exists", return_value=True):

        res = await inspector.inspect_page(
            workspace_id=1,
            source_id=10,
            page_number=3,
            filename="PID-101.pdf",
            visual_score=8.5,
            query="Check FV-302 valve location"
        )

        assert res.vlm_observation == mock_obs.description
        assert "FV-302" in res.equipment_tags
        assert "R-301" in res.equipment_tags
        assert "PT-101" in res.instrument_tags
        assert res.ocr_corroborated is True
        assert len(res.corroboration_results) == 1


@pytest.mark.asyncio
async def test_visual_evidence_inspector_missing_file_fallback():
    """Verify that when a file is absent on disk, a graceful fallback is produced without crashing."""
    inspector = VisualEvidenceInspector()
    with patch.object(inspector, "_resolve_file_path", return_value=None):
        res = await inspector.inspect_page(
            workspace_id=1,
            source_id=999,
            page_number=1,
            filename="missing.pdf",
            visual_score=4.5
        )
        assert "missing.pdf" in res.filename
        assert "4.50" in res.vlm_observation
        assert res.ocr_corroborated is None


@pytest.mark.asyncio
async def test_rca_evidence_acquirer_uses_real_vlm_observation():
    """Verify that RCAEvidenceAcquirer assigns real VLM observations rather than placeholder strings."""
    mock_text_retriever = AsyncMock()
    mock_text_retriever.retrieve.return_value = ("", [], [])

    mock_visual_retriever = AsyncMock()
    mock_visual_retriever.retrieve.return_value = [
        VisualSearchResult(
            workspace_id=1,
            source_id=5,
            processing_version="v1",
            page_number=2,
            filename="Reactor_PID.pdf",
            score=7.8
        )
    ]
    mock_visual_retriever._custom_provider = True

    mock_inspector = AsyncMock()
    mock_insp_res = VisualInspectionResult(
        workspace_id=1,
        source_id=5,
        filename="Reactor_PID.pdf",
        page_number=2,
        visual_score=7.8,
        vlm_observation="Observed FV-302 control valve installed upstream of R-301.",
        equipment_tags=["FV-302", "R-301"],
        ocr_corroborated=True
    )
    mock_inspector.inspect_page.return_value = mock_insp_res

    acquirer = RCAEvidenceAcquirer(
        text_retriever=mock_text_retriever,
        visual_retriever=mock_visual_retriever,
        allow_simulation=True,
        inspector=mock_inspector
    )
    acquirer.verify_asset_registration = AsyncMock(return_value=True)

    mock_db = AsyncMock()
    mock_db.execute.return_value = AsyncMock(fetchall=AsyncMock(return_value=[]), fetchone=AsyncMock(return_value=None))

    bundle = await acquirer.acquire_evidence(
        workspace_id=1,
        query="RCA for reactor feed line: check FV-302 and R-301 drawing",
        db=mock_db
    )

    # Check evidence items
    vis_items = [e for e in bundle.evidence_items if e.retrieval_channel == "visual"]
    assert len(vis_items) == 1
    item = vis_items[0]

    # Crucial assertion: Must NOT be the old generic placeholder
    assert "MaxSim relevance score" not in item.content
    assert "Observed FV-302 control valve installed upstream of R-301." in item.content
    assert "FV-302" in item.equipment_ids
    assert "R-301" in item.equipment_ids
