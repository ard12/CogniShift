"""
Phase 5 Tier-B Real OCR Integration Tests.
Executes the actual local RapidOCR engine (ONNX Runtime, 100% offline) against
known scanned fixtures to verify character extraction, confidence, and page provenance.
"""
import io
import pytest
from PIL import Image, ImageDraw

from cognishift.core.document_processing.schemas import (
    OCRResult,
    OCRUnavailableError
)
from cognishift.core.document_processing.ocr_provider import RapidOCREngine
from cognishift.core.document_processing.service import DocumentProcessingService
from cognishift.core.document_processing.lifecycle import idempotent_delete_source
from cognishift.core.retriever import retrieve_context
from cognishift.app.db.database import get_db, init_db


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_real_rapidocr_extracts_known_scanned_fixture():
    """
    Empirically verifies that the live local RapidOCR engine recognizes text
    from a rendered raster fixture with high confidence and bounding boxes.
    """
    engine = RapidOCREngine()
    assert await engine.health_check() is True

    # Generate fixture image with crisp text
    img = Image.new("RGB", (600, 150), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 50), "PUMP P-101A HIGH TEMPERATURE ALARM", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    result = await engine.extract(img_bytes)

    assert result.engine == "rapidocr"
    assert result.confidence is not None
    assert result.confidence > 0.80
    assert len(result.blocks) > 0
    # Text extracted must contain the equipment tag
    clean_extracted = result.text.replace(" ", "").upper()
    assert "PUMP" in clean_extracted
    assert any(k in clean_extracted for k in ["101A", "1O1A", "ALARM"])

    # Verify bounding boxes exist
    first_block = result.blocks[0]
    assert first_block.bbox is not None
    assert first_block.bbox.x2 > first_block.bbox.x1
    assert first_block.bbox.y2 > first_block.bbox.y1


@pytest.mark.asyncio
async def test_real_rapidocr_full_service_pipeline(tmp_path):
    """
    End-to-end integration: Image file -> RapidOCR -> Page chunks -> Chroma -> Retrieval.
    """
    img_path = tmp_path / "equipment_scan.png"
    img = Image.new("RGB", (600, 150), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 50), "TAG: HE-202 HEAT EXCHANGER TUBE LEAK", fill=(0, 0, 0))
    img.save(str(img_path))

    ws_id = 910
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (910, 'Real OCR WS')")
        cursor = await db.execute(
            "INSERT INTO knowledge_sources (workspace_id, name, source_type, processing_status) VALUES (910, 'equipment_scan.png', 'image', 'pending') RETURNING id"
        )
        sid = (await cursor.fetchone())["id"]
        await db.commit()

    engine = RapidOCREngine()
    service = DocumentProcessingService(ocr_provider=engine)

    try:
        res = await service.process_document(
            workspace_id=ws_id,
            source_id=sid,
            file_path=img_path,
            filename="equipment_scan.png"
        )

        assert res["status"] == "completed"
        assert res["ocr_pages"] == 1
        assert res["chunk_count"] >= 1

        # Query ChromaDB via retriever
        context = await retrieve_context(
            workspace_id=ws_id,
            query="heat exchanger leak tube",
            top_k=3,
            allowed_source_ids=[sid]
        )

        assert "equipment_scan.png" in context
        assert "HE-202" in context or "EXCHANGER" in context
    finally:
        await idempotent_delete_source(ws_id, sid)


@pytest.mark.asyncio
async def test_real_ocr_missing_assets_fails_closed():
    """
    Verifies that when local OCR engine is deliberately uninitialized,
    it raises OCRUnavailableError without attempting remote downloads or cloud APIs.
    """
    engine = RapidOCREngine()
    engine._engine = None  # Simulate missing local ONNX weights

    with pytest.raises(OCRUnavailableError) as exc:
        await engine.extract(b"FAKE_IMAGE")
    assert "Automatic cloud fallback is strictly prohibited" in str(exc.value)
