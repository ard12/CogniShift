"""
Comprehensive test suite for Hybrid Multimodal RAG with ColPali in CogniShift:
- Intent-aware channel weighting (Text vs Visual vs RCA)
- Reciprocal Rank Fusion (RRF) mathematical ranking
- LocalMultiVectorStore + ChromaDB integration
- All-or-nothing atomic activation & rollback on visual failure
- RCA Accuracy Mode independent execution guarantee
- Missing ColPali weights graceful fallback to Text RAG
"""
import io
import pytest
import pymupdf
import numpy as np
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from cognishift.app.config import settings
from cognishift.app.db.database import init_db, get_db
from cognishift.core.retrieval.evidence_fusion import EvidenceFusion, QueryIntentWeighting
from cognishift.core.retrieval.hybrid_retriever import HybridDocumentRetriever
from cognishift.core.retrieval.text_retriever import TextRetriever
from cognishift.core.retrieval.visual_retriever import VisualRetriever
from cognishift.core.visual_rag.schemas import VisualSearchResult, PageVectorMetadata
from cognishift.core.visual_rag.vector_store import LocalMultiVectorStore, get_visual_vector_store
from cognishift.core.visual_rag.embedding_provider import (
    SimulatedVisualEmbeddingProvider,
    get_visual_embedding_provider
)
from cognishift.core.document_processing.service import DocumentProcessingService
from cognishift.core.document_processing.lifecycle import idempotent_delete_source


def test_query_intent_weighting():
    """Verify dynamic channel weights: text vs visual vs RCA."""
    # Text-heavy
    cat, w_t, w_v = QueryIntentWeighting.determine_weights("What is the company leave policy and remote work SOP?")
    assert cat == "text"
    assert w_t == 0.8 and w_v == 0.2

    # Visual / Layout
    cat, w_t, w_v = QueryIntentWeighting.determine_weights("Show me the P&ID diagram and layout table for Heat Exchanger HEX-101")
    assert cat == "visual"
    assert w_t == 0.3 and w_v == 0.7

    # RCA / Diagnostic
    cat, w_t, w_v = QueryIntentWeighting.determine_weights("Conduct an RCA on the boiler trip: why did it trip and fail?")
    assert cat == "rca"
    assert w_t == 0.5 and w_v == 0.5


def test_evidence_fusion_rrf():
    """Verify Reciprocal Rank Fusion ranking and channel labeling."""
    fusion = EvidenceFusion(rrf_k=60)

    # Mock Text ranked items (Doc A Page 1 is #1, Doc B Page 2 is #2)
    text_items = [
        {
            "doc": "SOP procedural steps for startup",
            "meta": {"source_id": 1, "processing_version": "v1", "page": 1, "filename": "sop.pdf"},
            "score": 0.85,
            "page": 1,
            "source_id": 1,
            "filename": "sop.pdf"
        },
        {
            "doc": "Pump maintenance interval specifications",
            "meta": {"source_id": 2, "processing_version": "v1", "page": 2, "filename": "pump.pdf"},
            "score": 0.70,
            "page": 2,
            "source_id": 2,
            "filename": "pump.pdf"
        }
    ]

    # Mock Visual search results (Doc B Page 2 is #1, Doc C Page 5 is #2)
    visual_results = [
        VisualSearchResult(
            workspace_id=1,
            source_id=2,
            processing_version="v1",
            page_number=2,
            filename="pump.pdf",
            score=4.2
        ),
        VisualSearchResult(
            workspace_id=1,
            source_id=3,
            processing_version="v1",
            page_number=5,
            filename="schematic.pdf",
            score=3.8
        )
    ]

    fused = fusion.fuse(text_items, visual_results, query="Check pump P-101 diagram and maintenance schedule")

    # In a visual/layout query: Doc B Page 2 is present in BOTH text (#2) and visual (#1) channels => strong HYBRID candidate
    assert len(fused) == 3

    top_candidate = fused[0]
    assert top_candidate.source_id == 2
    assert top_candidate.page_number == 2
    assert top_candidate.retrieval_channel == "hybrid"
    assert "HYBRID" in top_candidate.citation

    # Check channels for other items
    channels = {c.source_id: c.retrieval_channel for c in fused}
    assert channels[1] == "text"
    assert channels[3] == "visual"


@pytest.mark.asyncio
async def test_hybrid_retriever_graceful_fallback_when_colpali_disabled():
    """Verify that when ColPali is disabled, HybridDocumentRetriever returns pure Text RAG context without crashing."""
    await init_db()

    mock_text_retriever = AsyncMock()
    mock_text_retriever.retrieve.return_value = (
        "[sop.pdf | Page 1 | NATIVE]: Startup procedure step 1.",
        [{"filename": "sop.pdf", "page": 1, "extraction_method": "NATIVE"}],
        [{"doc": "Startup procedure step 1", "score": 0.9, "page": 1, "source_id": 1, "filename": "sop.pdf"}]
    )

    # Empty visual retriever (ColPali weights missing or disabled)
    mock_vis_retriever = AsyncMock()
    mock_vis_retriever.retrieve.return_value = []

    retriever = HybridDocumentRetriever(
        text_retriever=mock_text_retriever,
        visual_retriever=mock_vis_retriever
    )

    ctx, metas = await retriever.retrieve(workspace_id=1, query="How to start boiler?")

    assert "[sop.pdf | Page 1 | NATIVE]" in ctx
    assert len(metas) == 1
    assert metas[0]["filename"] == "sop.pdf"


@pytest.mark.asyncio
async def test_end_to_end_multimodal_ingestion_and_atomic_lifecycle(tmp_path):
    """
    Verify end-to-end ingestion creates both text and visual index entries,
    and retirement/deletion cleans both stores.
    """
    await init_db()
    ws_id = 3001
    src_id = 401

    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, 'WS Multimodal')", (ws_id,))
        await db.execute(
            "INSERT OR IGNORE INTO knowledge_sources (id, workspace_id, name, source_type, original_filename) VALUES (?, ?, 'Plant_Manual.pdf', 'pdf', 'Plant_Manual.pdf')",
            (src_id, ws_id)
        )
        await db.commit()

    # Create a minimal 2-page test PDF
    pdf_path = tmp_path / "Plant_Manual.pdf"
    doc = pymupdf.open()
    # Page 1: Native text
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 100), "Standard Operating Procedure for Cooling Tower CT-101. Normal flow is 500 GPM.")
    # Page 2: Table text
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 100), "Equipment Tag | Pressure | Status\nPT-101 | 142.5 PSI | NORMAL\nV-102 | 350 bar | CLOSED")
    doc.save(str(pdf_path))
    doc.close()

    # Ingest using DocumentProcessingService with allow_simulation=True
    sim_provider = SimulatedVisualEmbeddingProvider(patch_tokens=16, vector_dim=64)
    service = DocumentProcessingService(
        visual_embedding_provider=sim_provider,
        allow_simulation=True
    )

    res = await service.process_document(
        workspace_id=ws_id,
        source_id=src_id,
        file_path=pdf_path,
        filename="Plant_Manual.pdf"
    )

    assert res["status"] == "completed"
    assert res["total_pages"] == 2
    assert res["visual_pages"] == 2
    active_ver = res["processing_version"]

    # Verify visual vectors exist in SQLite document_page_visual_index
    v_store = get_visual_vector_store()
    assert await v_store.count(ws_id) == 2

    # Verify hybrid retrieval finds both text and visual candidates
    vis_retriever = VisualRetriever(visual_provider=sim_provider, allow_simulation=True)
    hybrid_retriever = HybridDocumentRetriever(
        visual_retriever=vis_retriever,
        allow_simulation=True
    )

    ctx, metas = await hybrid_retriever.retrieve(
        workspace_id=ws_id,
        query="Check CT-101 flow and PT-101 pressure readings",
        top_k=3
    )

    assert len(metas) > 0
    assert any("Plant_Manual.pdf" in m["filename"] for m in metas)

    # Test Idempotent Deletion: Purges both text and visual vectors
    await idempotent_delete_source(workspace_id=ws_id, source_id=src_id)
    assert await v_store.count(ws_id) == 0


@pytest.mark.asyncio
async def test_all_or_nothing_activation_failure_preserves_old_generation(tmp_path):
    """
    Verify user mandate: processing_version must not activate until all enabled required indexes
    are successfully built. Failed visual indexing must preserve the previously active complete generation.
    """
    await init_db()
    ws_id = 4001
    src_id = 501

    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, 'WS Rollback')", (ws_id,))
        await db.execute(
            """INSERT OR IGNORE INTO knowledge_sources
               (id, workspace_id, name, source_type, active_processing_version, processing_status)
               VALUES (?, ?, 'OldDoc.pdf', 'pdf', 'gen_1_active', 'completed')""",
            (src_id, ws_id)
        )
        await db.commit()

    # Create dummy PDF
    pdf_path = tmp_path / "OldDoc.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Sample document content.")
    doc.save(str(pdf_path))
    doc.close()

    # Mock a faulty visual embedding provider that crashes during embed_page
    failing_provider = MagicMock()
    failing_provider.is_available.return_value = True
    failing_provider.embed_page.side_effect = RuntimeError("Visual model CUDA OOM or disk failure!")

    service = DocumentProcessingService(
        visual_embedding_provider=failing_provider,
        allow_simulation=True
    )

    with pytest.raises(RuntimeError, match="Visual model CUDA OOM"):
        await service.process_document(
            workspace_id=ws_id,
            source_id=src_id,
            file_path=pdf_path,
            filename="OldDoc.pdf"
        )

    # Critical Assertion: Old active generation MUST still be active in knowledge_sources!
    async with get_db() as db:
        cursor = await db.execute("SELECT active_processing_version, processing_status FROM knowledge_sources WHERE id = ?", (src_id,))
        row = await cursor.fetchone()
        assert row["active_processing_version"] == "gen_1_active"
        # Since gen_1_active is preserved, source status is not failed overall
        assert row["active_processing_version"] is not None


@pytest.mark.asyncio
async def test_rca_accuracy_mode_unsuppressed_by_router():
    """
    Verify user mandate: RCA Accuracy Mode must always execute text + visual + topology
    evidence retrieval independently of semantic-router classification.
    Router error (e.g. misclassifying as CONVERSATION) must never suppress an evidence channel.
    """
    from cognishift.core.engine import execute_agent_run
    from cognishift.core.semantic_router import SemanticRoutingResult, SemanticIntent

    await init_db()
    ws_id = 5001
    ag_id = 601
    src_id = 701

    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, 'WS RCA Test')", (ws_id,))
        await db.execute(
            """INSERT OR IGNORE INTO agent_definitions 
               (id, workspace_id, name, knowledge_source_ids) 
               VALUES (?, ?, 'RCA Inspector', '["701"]')""",
            (ag_id, ws_id)
        )
        await db.execute(
            """INSERT OR IGNORE INTO knowledge_sources
               (id, workspace_id, name, source_type, active_processing_version, processing_status)
               VALUES (?, ?, 'Heater_Manual.pdf', 'pdf', 'v1', 'completed')""",
            (src_id, ws_id)
        )
        await db.commit()

    # Simulate semantic router erroneously returning CONVERSATION
    bad_router_decision = SemanticRoutingResult(
        intent=SemanticIntent.CONVERSATION,
        confidence=0.95
    )

    from cognishift.core.providers import ModelResponse

    mock_sem_router = MagicMock()
    mock_sem_router.route.return_value = bad_router_decision

    with patch("cognishift.core.engine.get_semantic_router", return_value=mock_sem_router), \
         patch("cognishift.core.engine.retrieve_context_with_metadata", new=AsyncMock(return_value=("[Heater_Manual.pdf | Page 3 | VISUAL]: Fuel valve FV-101 failed open", [{"filename": "Heater_Manual.pdf", "page": 3}]))), \
         patch("cognishift.core.engine.query_graph_context", new=AsyncMock(return_value="HEX-101 connects to FV-101")), \
         patch("cognishift.core.engine.get_provider") as mock_gp:

        mock_resp = ModelResponse(
            text="Based on the P&ID and telemetry, the root cause of the heater trip was FV-101 failing open.",
            model_name="qwen2.5:7b",
            provider="ollama",
            success=True
        )

        mock_provider = AsyncMock()
        mock_provider.generate_text.return_value = mock_resp
        mock_provider.get_model_info = MagicMock(return_value={"status": "available"})
        mock_gp.return_value = mock_provider

        run_resp = await execute_agent_run(
            workspace_id=ws_id,
            agent_id=ag_id,
            input_text="Conduct an RCA on the heater trip: why did it trip and what is the root cause?"
        )

        assert run_resp.status == "completed"
        # Retrieval was NOT bypassed despite router saying CONVERSATION!
        assert "Heater_Manual.pdf | Page 3" in (run_resp.sources_used or "")
        assert "Plant Topology Graph" in (run_resp.sources_used or "")


