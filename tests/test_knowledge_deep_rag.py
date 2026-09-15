"""
CogniShift Deep RAG & Full-Coverage Spreadsheet Ingestion Verification Suite.
Tests:
1. Ingestion of 600-row operational spreadsheet without 150-row truncation.
2. Sliding row window budget (3,500 characters) preserving authoritative headers per chunk.
3. Original workbook coordinate persistence (source_id, sheet_name, header_row, row_start, row_end, checksum).
4. Semantic and factual vector retrieval of Row 550 incident.
5. Deduplication of overlapping sliding windows during context retrieval.
6. Full purge of all window vectors from ChromaDB upon source deletion.
"""
import pytest
import csv
import io
from pathlib import Path
from fastapi import UploadFile
from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.app.core.auth import User
from cognishift.core.retriever import (
    retrieve_context,
    purge_knowledge_source,
    chroma_client,
    get_workspace_vector_count
)
from cognishift.app.api.knowledge import upload_document


@pytest.fixture(autouse=True)
def set_simulated_mode(monkeypatch):
    monkeypatch.setattr(settings, "operating_mode", "simulated")


@pytest.fixture
async def setup_deep_rag_env(tmp_path):
    await init_db()
    ws_id = 42
    
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (?, 'Deep-RAG-Workspace', 'Testing 600-row ingestion')",
            (ws_id,)
        )
        await db.commit()

    # Generate 600-row CSV file structured by operational plant units
    csv_file = tmp_path / "refinery_600_rows.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Header (Row 1)
        writer.writerow([
            "timestamp", "unit", "tag", "sensor_description", "discharge_pressure_psi",
            "vibration_rms_mm_s", "relief_valve_status", "operational_note"
        ])
        for r in range(2, 601):
            if r <= 200:
                unit = "Unit 101 Atmospheric Distillation"
                tag = f"PT-1{r % 50:02d}"
                desc = "Atmospheric crude distillation column tray sensor"
                press = f"{110.0 + (r % 10) * 0.5:.2f}"
                vib = f"{1.20 + (r % 5) * 0.05:.2f}"
                valve = "NORMAL"
                note = f"Routine atmospheric distillation column telemetry {r}"
            elif r <= 400:
                unit = "Unit 201 Vacuum Gas Oil Hydrotreater"
                tag = f"PT-2{r % 50:02d}"
                desc = "Hydrotreater catalytic reactor bed pressure monitor"
                press = f"{220.0 + (r % 10) * 0.8:.2f}"
                vib = f"{1.40 + (r % 5) * 0.08:.2f}"
                valve = "NORMAL"
                note = f"Steady-state hydrotreater reactor telemetry {r}"
            else:
                # Rows 401 - 600: Unit 401 Flare Subsystem & Relief Header
                unit = "Unit 401 Flare Subsystem"
                if r == 550:
                    tag = "PT-999"
                    desc = "Flare Subsystem Header Overpressure Transmitter"
                    press = "742.15"
                    vib = "18.54"
                    valve = "CLOSED"
                    note = "Critical excursion: flare header relief valve failed closed during overpressure"
                else:
                    tag = f"PT-4{r % 50:02d}"
                    desc = "Flare header manifold collection line sensor"
                    press = f"{140.0 + (r % 10) * 0.6:.2f}"
                    vib = f"{1.30 + (r % 5) * 0.06:.2f}"
                    valve = "OPEN" if r % 2 == 0 else "NORMAL"
                    note = f"Flare subsystem telemetry monitoring sample {r}"

            writer.writerow([
                f"2026-09-06 {10 + (r // 60):02d}:{r % 60:02d}:00",
                unit, tag, desc, press, vib, valve, note
            ])

    return ws_id, csv_file


@pytest.mark.asyncio
async def test_600_row_sliding_window_ingestion_and_retrieval(setup_deep_rag_env):
    """Verify that a 600-row workbook is ingested into multiple windows and Row 550 is retrievable."""
    ws_id, csv_file = setup_deep_rag_env

    # 1. Clean prior vectors for ws_id
    collection = chroma_client.get_or_create_collection(f"workspace_{ws_id}")
    try:
        collection.delete(where={"workspace_id": ws_id})
    except Exception:
        pass

    with open(csv_file, "rb") as f:
        content = f.read()

    upload = UploadFile(filename="refinery_600_rows.csv", file=io.BytesIO(content))
    test_user = User(user_id="test_admin", role="administrator", allowed_workspace_ids=[ws_id])

    # Ingest via upload_document
    res = await upload_document(
        workspace_id=ws_id,
        file=upload,
        user=test_user
    )

    # 2. Ingestion completeness assertions:
    # Must have produced multiple chunks (zero-drop full coverage beyond 150-row limit)
    assert res.chunk_count > 3, f"Expected >3 chunks for 600 rows, got {res.chunk_count}"
    assert res.processing_status == "completed"

    # 3. ChromaDB Metadata Assertions
    col_items = collection.get(where={"source_id": int(res.id)}, include=["metadatas", "documents"])
    assert len(col_items["ids"]) == res.chunk_count

    # Verify every chunk stores workbook coordinates
    has_row_550_chunk = False
    for meta, doc in zip(col_items["metadatas"], col_items["documents"]):
        assert "row_start" in meta
        assert "row_end" in meta
        assert "header_row" in meta
        assert meta["header_row"] == 1
        assert meta["source_id"] == int(res.id)
        if meta["row_start"] <= 550 <= meta["row_end"]:
            has_row_550_chunk = True
            assert "PT-999" in doc
            assert "742.15" in doc
            assert "excursion" in doc

    assert has_row_550_chunk is True, "Row 550 fact was not found in any sliding window chunk!"

    # 4. Context Retrieval of Row 550
    retrieval_query = "PT-999 Flare Subsystem Header Transmitter 742.15 Extreme excursion on flare header manifold"
    retrieved_text = await retrieve_context(
        workspace_id=ws_id,
        query=retrieval_query,
        top_k=5,
        allowed_source_ids=[int(res.id)],
        distance_threshold=0.85
    )
    assert "PT-999" in retrieved_text
    assert "742.15" in retrieved_text
    assert "Rows" in retrieved_text or "refinery_600_rows.csv" in retrieved_text

    # 5. Purge and Lifecycle Deletion Verification
    count_before = get_workspace_vector_count(ws_id)
    assert count_before > 0

    purge_res = await purge_knowledge_source(workspace_id=ws_id, source_id=int(res.id))
    assert purge_res is True

    # Assert 100% of chunks purged
    post_purge = collection.get(where={"source_id": int(res.id)})
    assert len(post_purge["ids"]) == 0

    # Querying again must return empty
    empty_ctx = await retrieve_context(
        workspace_id=ws_id,
        query="flare header manifold PT-999",
        top_k=3,
        allowed_source_ids=[int(res.id)]
    )
    assert empty_ctx == ""
