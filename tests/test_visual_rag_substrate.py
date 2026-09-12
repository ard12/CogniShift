"""
Unit tests for Visual RAG Substrate:
- MaxSim mathematical correctness
- LocalMultiVectorStore persistence, isolation, version retirement, and deletion
- SimulatedVisualEmbeddingProvider deterministic outputs & policy
- DeterministicPageVerifier OCR corroboration
"""
import pytest
import numpy as np
from pathlib import Path
from cognishift.app.config import settings
from cognishift.app.db.database import init_db, get_db
from cognishift.core.visual_rag.vector_store import (
    compute_maxsim,
    LocalMultiVectorStore,
    get_visual_vector_store
)
from cognishift.core.visual_rag.schemas import PageVectorMetadata
from cognishift.core.visual_rag.embedding_provider import (
    SimulatedVisualEmbeddingProvider,
    get_visual_embedding_provider
)
from cognishift.core.visual_rag.page_verifier import DeterministicPageVerifier


def test_maxsim_mathematical_properties():
    """Verify late-interaction MaxSim: sum over query tokens of max dot product across doc tokens."""
    # Query: 2 tokens, dim 4
    # Doc A: 3 tokens, dim 4 - high similarity
    # Doc B: 3 tokens, dim 4 - orthogonal
    q = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0]
    ], dtype=np.float32)

    doc_a = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0]
    ], dtype=np.float32)

    doc_b = np.array([
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
        [0.0, 0.0, 1.0, 0.0]
    ], dtype=np.float32)

    score_a = compute_maxsim(q, doc_a)
    score_b = compute_maxsim(q, doc_b)

    # For doc_a: q[0] matches doc_a[0] (dot=1), q[1] matches doc_a[1] (dot=1) => sum = 2.0
    assert pytest.approx(score_a, rel=1e-3) == 2.0
    # For doc_b: q[0] and q[1] have dot=0 with all doc_b tokens => sum = 0.0
    assert pytest.approx(score_b, rel=1e-3) == 0.0
    assert score_a > score_b


def test_simulated_embedding_provider_policy():
    """Verify simulated provider is deterministic and factory obeys allow_simulation policy."""
    sim = SimulatedVisualEmbeddingProvider(patch_tokens=16, vector_dim=64)
    img_data = b"dummy_png_bytes_for_testing"
    emb1 = sim.embed_page(img_data)
    emb2 = sim.embed_page(img_data)

    assert emb1.shape == (16, 64)
    assert np.allclose(emb1, emb2)

    q_emb = sim.embed_query("check pump pressure PT-101")
    assert q_emb.ndim == 2
    assert q_emb.shape[1] == 64

    # Runtime check: when colpali is disabled, provider returns None
    from unittest.mock import patch
    with patch.object(settings, "colpali_enabled", False):
        prov_runtime = get_visual_embedding_provider(allow_simulation=False)
        assert prov_runtime is None


@pytest.mark.asyncio
async def test_local_multi_vector_store_crud_and_isolation(tmp_path):
    """Verify LocalMultiVectorStore upsert, query, workspace isolation, and purge."""
    await init_db()
    store = LocalMultiVectorStore()

    ws1 = 1001
    ws2 = 1002
    src1 = 201
    src2 = 202
    ver1 = "v1_alpha"
    ver2 = "v2_beta"

    # Seed workspaces in DB
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, 'WS 1')", (ws1,))
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, 'WS 2')", (ws2,))
        await db.execute("INSERT OR IGNORE INTO knowledge_sources (id, workspace_id, name, source_type) VALUES (?, ?, 'Doc1', 'pdf')", (src1, ws1))
        await db.execute("INSERT OR IGNORE INTO knowledge_sources (id, workspace_id, name, source_type) VALUES (?, ?, 'Doc2', 'pdf')", (src2, ws2))
        await db.commit()

    dim = 32
    sim_provider = SimulatedVisualEmbeddingProvider(patch_tokens=10, vector_dim=dim)

    # Upsert Page 1 for ws1, src1, ver1
    meta1 = PageVectorMetadata(
        workspace_id=ws1,
        source_id=src1,
        processing_version=ver1,
        page_number=1,
        filename="pump_manual.pdf",
        checksum="hash_page_1"
    )
    vec1 = sim_provider.embed_page(b"page_1_image")
    await store.upsert_page(ws1, src1, ver1, 1, vec1, meta1)

    # Upsert Page 2 for ws1, src1, ver1
    meta2 = PageVectorMetadata(
        workspace_id=ws1,
        source_id=src1,
        processing_version=ver1,
        page_number=2,
        filename="pump_manual.pdf",
        checksum="hash_page_2"
    )
    vec2 = sim_provider.embed_page(b"page_2_image")
    await store.upsert_page(ws1, src1, ver1, 2, vec2, meta2)

    # Upsert Page 1 for ws2, src2, ver1
    meta_ws2 = PageVectorMetadata(
        workspace_id=ws2,
        source_id=src2,
        processing_version=ver1,
        page_number=1,
        filename="other_manual.pdf",
        checksum="hash_ws2"
    )
    vec_ws2 = sim_provider.embed_page(b"ws2_page")
    await store.upsert_page(ws2, src2, ver1, 1, vec_ws2, meta_ws2)

    # 1. Check workspace counts
    assert await store.count(ws1) == 2
    assert await store.count(ws2) == 1

    # 2. Query workspace 1 - must NEVER return workspace 2 vectors (Strict Isolation)
    q_vec = sim_provider.embed_query("pump troubleshooting")
    results_ws1 = await store.query_maxsim(ws1, q_vec, top_k=5)
    assert len(results_ws1) == 2
    assert all(r.workspace_id == ws1 for r in results_ws1)
    assert all(r.source_id == src1 for r in results_ws1)

    # 3. Test version retirement
    # Simulate reprocessing src1 with ver2
    meta1_v2 = PageVectorMetadata(
        workspace_id=ws1,
        source_id=src1,
        processing_version=ver2,
        page_number=1,
        filename="pump_manual.pdf",
        checksum="hash_page_1_v2"
    )
    vec1_v2 = sim_provider.embed_page(b"page_1_v2")
    await store.upsert_page(ws1, src1, ver2, 1, vec1_v2, meta1_v2)
    assert await store.count(ws1) == 3

    # Purge old generations: keep only ver2
    await store.purge_old_generations(ws1, src1, active_version=ver2)
    assert await store.count(ws1) == 1

    results_after_retire = await store.query_maxsim(ws1, q_vec, top_k=5)
    assert len(results_after_retire) == 1
    assert results_after_retire[0].processing_version == ver2

    # 4. Test purge source
    await store.purge_source(ws1, src1)
    assert await store.count(ws1) == 0

    # WS 2 must remain completely intact
    assert await store.count(ws2) == 1
    await store.purge_workspace(ws2)
    assert await store.count(ws2) == 0


@pytest.mark.asyncio
async def test_page_verifier_corroboration():
    """Verify DeterministicPageVerifier correctly corroborates matching numbers and tags."""
    await init_db()
    verifier = DeterministicPageVerifier()

    ws = 2001
    sid = 301
    ver = "v1"
    page_num = 1

    # Seed document_pages with OCR text
    ocr_text = "Discharge pressure transmitter PT-101 reads 142.5 PSI. Vessel V-102 operating at 350 bar."
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, 'WS Verifier')", (ws,))
        await db.execute("INSERT OR IGNORE INTO knowledge_sources (id, workspace_id, name, source_type) VALUES (?, ?, 'P&ID.pdf', 'pdf')", (sid, ws))
        await db.execute(
            """INSERT OR REPLACE INTO document_pages
               (workspace_id, source_id, processing_version, page_number, extraction_method, text_content)
               VALUES (?, ?, ?, ?, 'ocr', ?)""",
            (ws, sid, ver, page_num, ocr_text)
        )
        await db.commit()

    # VLM observation containing matching tags and numbers + one hallucinated number
    vlm_output = "The diagram shows pressure gauge PT-101 with reading 142.5 PSI, and a relief valve set to 999 PSI."

    results = await verifier.verify_page_claims(
        workspace_id=ws,
        source_id=sid,
        processing_version=ver,
        page_number=page_num,
        vlm_observation=vlm_output
    )

    tags = [r for r in results if r.claim_type == "instrument_tag"]
    assert any(t.claimed_value == "PT-101" and t.corroborated for t in tags)

    readings = [r for r in results if r.claim_type in ["reading_with_unit", "numeric"]]
    assert any("142.5" in r.claimed_value and r.corroborated for r in readings)
    assert any("999" in r.claimed_value and not r.corroborated for r in readings)

    summary = verifier.format_corroboration_summary(results)
    assert "OCR Corroborated" in summary
    assert "PT-101" in summary
    assert "Uncorroborated" in summary
    assert "999" in summary
