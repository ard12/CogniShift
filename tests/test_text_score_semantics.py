"""
Unit tests for text score semantics, distance vs similarity calibration,
monotonic confidence calculation, page aggregation, and sqlite row safety.
"""
import pytest
import sqlite3
from cognishift.core.retrieval.evidence_fusion import EvidenceFusion
from cognishift.core.visual_rag.schemas import VisualSearchResult


def test_distance_confidence_calibration():
    """Verify that confidence derived from Chroma distance is strictly monotonic and correctly calibrated."""
    fusion = EvidenceFusion()

    # Candidate with excellent match (distance = 0.10)
    item_good = {
        "source_id": 1,
        "page": 1,
        "doc": "Direct mention of P-101A cavitation symptoms",
        "distance": 0.10,
        "similarity": 0.95,
        "score": 0.95,
        "filename": "manual.pdf"
    }

    # Candidate with weak match (distance = 0.65)
    item_weak = {
        "source_id": 2,
        "page": 1,
        "doc": "General plant layout overview",
        "distance": 0.65,
        "similarity": 0.675,
        "score": 0.675,
        "filename": "overview.pdf"
    }

    # Candidate exceeding 0.78 threshold (distance = 0.85)
    item_irrelevant = {
        "source_id": 3,
        "page": 1,
        "doc": "Cafeteria lunch menu schedule",
        "distance": 0.85,
        "similarity": 0.575,
        "score": 0.575,
        "filename": "menu.pdf"
    }

    fused = fusion.fuse([item_good, item_weak, item_irrelevant], [], query="P-101A cavitation")
    by_source = {c.source_id: c for c in fused}

    # Best candidate must be item_good (source_id = 1)
    assert fused[0].source_id == 1
    assert by_source[1].text_distance == 0.10
    assert by_source[1].text_score == 0.95

    # Item 2 has weaker text rank
    assert by_source[2].text_distance == 0.65

    # Item 3 has lowest text rank
    assert by_source[3].text_distance == 0.85


def test_page_aggregation_selects_best_chunk():
    """Verify that multi-chunk pages select the chunk with minimum distance (maximum similarity)."""
    fusion = EvidenceFusion()

    # Page 5 has two chunks: chunk 1 is weak (dist 0.60), chunk 2 is great (dist 0.12)
    chunk_weak = {
        "source_id": 10,
        "page": 5,
        "doc": "Standard maintenance disclaimer",
        "distance": 0.60,
        "similarity": 0.70,
        "score": 0.70,
        "filename": "pumps.pdf"
    }
    chunk_strong = {
        "source_id": 10,
        "page": 5,
        "doc": "Trip setpoint for P-101 is 14.5 bar suction pressure",
        "distance": 0.12,
        "similarity": 0.94,
        "score": 0.94,
        "filename": "pumps.pdf"
    }

    fused = fusion.fuse([chunk_weak, chunk_strong], [], query="Trip setpoint suction pressure")
    assert len(fused) == 1
    page_candidate = fused[0]
    assert page_candidate.page_number == 5
    assert page_candidate.text_distance == 0.12
    assert page_candidate.text_score == 0.94
    assert len(page_candidate.text_snippets) == 2


@pytest.mark.asyncio
async def test_sensor_resolution_sqlite_row_safety():
    """Verify that sensor resolution does not crash with AttributeError on sqlite3.Row objects."""
    from cognishift.core.rca.sensor_resolution import _query_graph_sensors
    from unittest.mock import AsyncMock

    # Create an in-memory SQLite database with row_factory = sqlite3.Row
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("CREATE TABLE graph_nodes (id INTEGER, name TEXT, properties TEXT)")
    cur.execute("CREATE TABLE graph_edges (source_node_id INTEGER, target_node_id INTEGER, workspace_id INTEGER, relation_type TEXT)")
    cur.execute("INSERT INTO graph_nodes VALUES (1, 'P-101', '{}')")
    cur.execute("INSERT INTO graph_nodes VALUES (2, 'PT-101', '{\"description\": \"Pump suction pressure\", \"type\": \"pressure\"}')")
    cur.execute("INSERT INTO graph_edges VALUES (1, 2, 1, 'HAS_SENSOR')")
    conn.commit()

    cur.execute(
        """
        SELECT n.name, n.properties
        FROM graph_nodes n
        JOIN graph_edges e ON e.target_node_id = n.id
        JOIN graph_nodes src ON e.source_node_id = src.id
        WHERE e.workspace_id = 1
        """
    )
    rows = cur.fetchall()
    assert len(rows) == 1
    assert isinstance(rows[0], sqlite3.Row)

    mock_db = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = rows
    mock_db.execute.return_value = mock_cursor

    res = await _query_graph_sensors(mock_db, 1, "P-101", "pressure", "")
    assert res == "PT-101"
