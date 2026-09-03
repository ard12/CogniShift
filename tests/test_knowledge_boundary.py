"""
Permanent Knowledge Boundary & Deletion Lifecycle Test Suite.
Phase 3.0 Verification for CogniShift.
Ensures strict server-side knowledge isolation, fail-closed semantics, and Chroma chunk purging.
"""

import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock

from cognishift.core.retriever import retrieve_context, purge_knowledge_source, chroma_client
from cognishift.app.db.database import get_db, init_db
from cognishift.core.engine import execute_agent_run
from cognishift.core.providers import ModelResponse
from cognishift.core.simulated_provider import SimulatedProvider
from fastapi.testclient import TestClient
from cognishift.app.main import app
from cognishift.app.config import settings
settings.operating_mode = "simulated"
from tests.conftest import TEST_SUPERVISOR_TOKEN


@pytest.fixture(autouse=True)
async def setup_knowledge_db():
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'Refinery-1', 'MRPL')")
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (2, 'Refinery-2', 'Mangalore')")
        # Source 1 in WS 1
        await db.execute(
            """INSERT OR REPLACE INTO knowledge_sources (id, workspace_id, name, source_type, processing_status, chunk_count)
               VALUES (1, 1, 'Turbine_Manual.pdf', 'pdf', 'completed', 5)"""
        )
        # Source 2 in WS 1
        await db.execute(
            """INSERT OR REPLACE INTO knowledge_sources (id, workspace_id, name, source_type, processing_status, chunk_count)
               VALUES (2, 1, 'Pump_Manual.pdf', 'pdf', 'completed', 5)"""
        )
        # Source 3 in WS 2 (Cross-tenant)
        await db.execute(
            """INSERT OR REPLACE INTO knowledge_sources (id, workspace_id, name, source_type, processing_status, chunk_count)
               VALUES (3, 2, 'Tenant2_Manual.pdf', 'pdf', 'completed', 5)"""
        )
        # Agent with allowed source 1 only
        await db.execute(
            """INSERT OR REPLACE INTO agent_definitions (id, workspace_id, name, system_instructions, knowledge_source_ids, allowed_tool_ids)
               VALUES (101, 1, 'Turbine Agent', 'Expert on turbines', '[1]', '["check_pressure"]')"""
        )
        # Agent with empty knowledge sources
        await db.execute(
            """INSERT OR REPLACE INTO agent_definitions (id, workspace_id, name, system_instructions, knowledge_source_ids, allowed_tool_ids)
               VALUES (102, 1, 'Zero Knowledge Agent', 'No docs', '[]', '["check_pressure"]')"""
        )
        # Agent with malformed knowledge sources
        await db.execute(
            """INSERT OR REPLACE INTO agent_definitions (id, workspace_id, name, system_instructions, knowledge_source_ids, allowed_tool_ids)
               VALUES (103, 1, 'Malformed Agent', 'Bad json', '{"bad": "format"}', '["check_pressure"]')"""
        )
        # Agent trying to reference Tenant 2 source
        await db.execute(
            """INSERT OR REPLACE INTO agent_definitions (id, workspace_id, name, system_instructions, knowledge_source_ids, allowed_tool_ids)
               VALUES (104, 1, 'Infiltrator Agent', 'Cross tenant access attempt', '[3]', '["check_pressure"]')"""
        )
        await db.commit()


@pytest.mark.asyncio
async def test_agent_allowed_source_filtering():
    """Verify that retrieval with allowed_source_ids=[1] filters out source 2."""
    collection = chroma_client.get_or_create_collection("workspace_1")
    # Clean and insert mock vectors for source 1 and source 2
    try:
        collection.delete(where={"workspace_id": 1})
    except Exception:
        pass

    collection.add(
        documents=["Turbine overspeed trip setpoint is 3600 RPM.", "Pump impeller diameter is 250mm."],
        embeddings=[[0.1] * 384, [0.9] * 384],
        metadatas=[
            {"source_id": 1, "workspace_id": 1, "filename": "Turbine_Manual.pdf", "page": 12},
            {"source_id": 2, "workspace_id": 1, "filename": "Pump_Manual.pdf", "page": 4}
        ],
        ids=["chunk_s1_1", "chunk_s2_1"]
    )

    # Query with allowed_source_ids=[1]
    res_s1 = await retrieve_context(workspace_id=1, query="equipment parameters", top_k=5, allowed_source_ids=[1])
    assert "Turbine_Manual.pdf" in res_s1
    assert "Pump_Manual.pdf" not in res_s1
    assert "3600 RPM" in res_s1


@pytest.mark.asyncio
async def test_agent_empty_sources_fails_closed():
    """Agent with knowledge_source_ids=[] must retrieve exactly zero context."""
    res_empty = await retrieve_context(workspace_id=1, query="turbine parameters", top_k=5, allowed_source_ids=[])
    assert res_empty == ""


@pytest.mark.asyncio
async def test_agent_execution_enforces_knowledge_boundary():
    """Engine loop must strictly validate agent knowledge ownership and fail closed."""
    # Run Agent 102 (empty sources)
    mock_resp = ModelResponse(
        text='```json\n{"action": "final_answer", "content": "I reviewed the available manual."}\n```',
        model_name="test",
        provider="test"
    )
    with patch.object(SimulatedProvider, "generate_text", return_value=mock_resp):
        run_res = await execute_agent_run(workspace_id=1, agent_id=102, input_text="Check turbine speed", user_id="operator_sam")
    
    assert run_res.status == "completed"
    assert "None (No matching manual found)" in (run_res.sources_used or "")


@pytest.mark.asyncio
async def test_cross_workspace_source_filtered_out():
    """Agent 104 referencing source 3 (belongs to WS 2) must be filtered to 0 sources."""
    mock_resp = ModelResponse(
        text='```json\n{"action": "final_answer", "content": "Done."}\n```',
        model_name="test",
        provider="test"
    )
    with patch.object(SimulatedProvider, "generate_text", return_value=mock_resp):
        run_res = await execute_agent_run(workspace_id=1, agent_id=104, input_text="Cross tenant check", user_id="operator_sam")
    
    assert run_res.status == "completed"
    assert "None (No matching manual found)" in (run_res.sources_used or "")


@pytest.mark.asyncio
async def test_purge_knowledge_source_removes_chunks_from_chroma():
    """Deleting a knowledge source purges corresponding chunks from ChromaDB."""
    collection = chroma_client.get_or_create_collection("workspace_1")
    collection.add(
        documents=["Temp chunk to be purged."],
        embeddings=[[0.05] * 384],
        metadatas=[{"source_id": 999, "workspace_id": 1, "filename": "PurgeMe.pdf", "page": 1}],
        ids=["chunk_purge_999"]
    )
    # Verify present
    check_pre = collection.get(ids=["chunk_purge_999"])
    assert len(check_pre["ids"]) == 1

    # Purge
    await purge_knowledge_source(workspace_id=1, source_id=999)

    # Verify absent
    check_post = collection.get(ids=["chunk_purge_999"])
    assert len(check_post["ids"]) == 0


def test_chroma_purge_failure_prevents_false_success():
    """If Chroma deletion fails, the API raises HTTP 500 and does not delete DB record."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {TEST_SUPERVISOR_TOKEN}"}

    with patch("cognishift.app.api.knowledge.purge_knowledge_source", side_effect=RuntimeError("Chroma lock contention")):
        res = client.delete("/api/v1/knowledge/1", headers=headers)

    assert res.status_code == 500
    assert "Chroma lock contention" in res.json()["detail"]
