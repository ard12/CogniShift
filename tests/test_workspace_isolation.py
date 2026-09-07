import pytest
import asyncio
from pathlib import Path
import chromadb

from cognishift.app.db.database import get_db
from cognishift.core.security import (
    ensure_workspace_layout,
    get_workspace_root,
    resolve_workspace_path,
    SecurityError
)
from cognishift.core.retriever import retrieve_context, chroma_client, embedding_model


@pytest.mark.asyncio
async def test_workspace_creation_and_filesystem_layout():
    """Pillar 1: Verifies directory structure layout and strict path traversal prevention."""
    ws_a = 901
    ws_b = 902

    # 1. Ensure directory layouts
    root_a = ensure_workspace_layout(ws_a)
    root_b = ensure_workspace_layout(ws_b)

    assert root_a.exists() and root_a.is_dir()
    assert root_b.exists() and root_b.is_dir()
    assert (root_a / "documents").exists()
    assert (root_a / "uploads").exists()
    assert (root_b / "documents").exists()

    # 2. Write a private file into Workspace A
    secret_file = root_a / "documents" / "cdu_secret_parameters.txt"
    secret_file.write_text("CONFIDENTIAL_CRUDE_UNIT_DATA_901", encoding="utf-8")

    # 3. Attempt path traversal from Workspace B into Workspace A -> Must FAIL with SecurityError
    with pytest.raises(SecurityError):
        resolve_workspace_path(ws_b, f"../../{ws_a}/documents/cdu_secret_parameters.txt", purpose="read")


@pytest.mark.asyncio
async def test_workspace_vector_store_isolation():
    """Pillar 2: Verifies ChromaDB collection isolation (zero cross-tenant semantic bleed)."""
    ws_a = 903  # Refining / Process Safety
    ws_b = 904  # Corporate Financial Audit

    col_a_name = f"workspace_{ws_a}"
    col_b_name = f"workspace_{ws_b}"

    # Clean up collections if existing
    for name in [col_a_name, col_b_name]:
        try:
            chroma_client.delete_collection(name)
        except Exception:
            pass

    col_a = chroma_client.get_or_create_collection(col_a_name)
    col_b = chroma_client.get_or_create_collection(col_b_name)

    # Insert technical safety chunk into Workspace A
    text_a = "OISD-STD-106: Safety relief valve SV-401 has critical setpoint 450 PSI on Reactor-B."
    emb_a = list(embedding_model.embed([text_a]))[0].tolist()
    col_a.upsert(
        documents=[text_a],
        embeddings=[emb_a],
        metadatas=[{"source_id": 9031, "workspace_id": ws_a, "document_name": "OISD-106.pdf", "page_number": 1}],
        ids=["chunk_safety_1"]
    )

    # Insert financial chunk into Workspace B
    text_b = "MRPL Financial Audit: FY 2025-26 Gross Revenue reached 121800 Crores with 30.93% PAT growth."
    emb_b = list(embedding_model.embed([text_b]))[0].tolist()
    col_b.upsert(
        documents=[text_b],
        embeddings=[emb_b],
        metadatas=[{"source_id": 9041, "workspace_id": ws_b, "document_name": "Financial_History.xlsx", "page_number": 1}],
        ids=["chunk_finance_1"]
    )

    # Query Workspace A for Financial metrics -> Must NOT find Workspace B's financial data
    retrieved_in_a = await retrieve_context(workspace_id=ws_a, query="What was the FY26 gross revenue in crores?")
    assert "121800" not in retrieved_in_a
    assert "Financial Audit" not in retrieved_in_a

    # Query Workspace B for Safety relief valve -> Must NOT find Workspace A's valve data
    retrieved_in_b = await retrieve_context(workspace_id=ws_b, query="What is the critical setpoint for SV-401?")
    assert "SV-401" not in retrieved_in_b
    assert "Reactor-B" not in retrieved_in_b

    # Verify each workspace retrieves its OWN data accurately
    own_a = await retrieve_context(workspace_id=ws_a, query="SV-401 critical relief setpoint pressure")
    assert "SV-401" in own_a
    assert "450 PSI" in own_a

    own_b = await retrieve_context(workspace_id=ws_b, query="Gross revenue FY 2025-26")
    assert "121800" in own_b


@pytest.mark.asyncio
async def test_workspace_artifact_isolation():
    """Pillar 3: Verifies that artifacts generated in Workspace A are inaccessible in Workspace B."""
    ws_a = 905
    ws_b = 906

    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, ?)", (ws_a, "Artifact Unit A"))
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, ?)", (ws_b, "Artifact Unit B"))

        # Register artifact in Workspace A
        await db.execute(
            """INSERT INTO workspace_artifacts 
               (workspace_id, filename, relative_path, file_size, sha256_hash, artifact_type, title, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ws_a, "cdu_unit_audit.docx", "generated/cdu_unit_audit.docx", 25000, "hash_a_123", "docx", "CDU Audit", "Private")
        )
        await db.commit()

        # Query artifacts for Workspace B
        cursor_b = await db.execute("SELECT * FROM workspace_artifacts WHERE workspace_id = ?", (ws_b,))
        rows_b = await cursor_b.fetchall()
        assert len(rows_b) == 0

        # Query artifacts for Workspace A
        cursor_a = await db.execute("SELECT * FROM workspace_artifacts WHERE workspace_id = ?", (ws_a,))
        rows_a = await cursor_a.fetchall()
        assert len(rows_a) == 1
        assert rows_a[0]["filename"] == "cdu_unit_audit.docx"


@pytest.mark.asyncio
async def test_workspace_agent_and_run_isolation():
    """Pillar 4: Verifies that agent definitions and execution runs are isolated per workspace."""
    ws_a = 907
    ws_b = 908

    async with get_db() as db:
        # Create workspaces
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, ?)", (ws_a, "Unit A"))
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, ?)", (ws_b, "Unit B"))

        # Create Agent in Workspace A
        cur_ag = await db.execute(
            """INSERT INTO agent_definitions (workspace_id, name, description, allowed_tool_ids)
               VALUES (?, ?, ?, ?) RETURNING id""",
            (ws_a, "Safety Inspector A", "Monitors CDU", "['check_pressure']")
        )
        ag_id = (await cur_ag.fetchone())["id"]

        # Log Run in Workspace A
        await db.execute(
            """INSERT INTO agent_runs (id, workspace_id, agent_id, input_text, status, result_text)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (99071, ws_a, ag_id, "Check PT-101", "completed", "Nominal 105 PSI")
        )
        await db.commit()

        # Query agents for Workspace B -> Must be empty
        cur_b_ag = await db.execute("SELECT * FROM agent_definitions WHERE workspace_id = ?", (ws_b,))
        assert len(await cur_b_ag.fetchall()) == 0

        # Query runs for Workspace B -> Must NOT include Run #99071
        cur_b_runs = await db.execute("SELECT * FROM agent_runs WHERE workspace_id = ?", (ws_b,))
        b_runs = await cur_b_runs.fetchall()
        assert not any(r["id"] == 99071 for r in b_runs)


@pytest.mark.asyncio
async def test_workspace_shift_approval_isolation():
    """Pillar 5: Verifies that human-in-the-loop approvals are partitioned strictly by workspace."""
    ws_a = 909
    ws_b = 910

    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, ?)", (ws_a, "Unit A Approvals"))
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, ?)", (ws_b, "Unit B Approvals"))

        # Insert tool definition if not existing
        cur_tool = await db.execute("SELECT id FROM tool_definitions WHERE name = 'emergency_pressure_relief'")
        tool_row = await cur_tool.fetchone()
        if not tool_row:
            cur_t = await db.execute(
                "INSERT INTO tool_definitions (name, description, implementation_key) VALUES (?, ?, ?) RETURNING id",
                ("emergency_pressure_relief", "Relief valve actuation", "emergency_pressure_relief")
            )
            tool_id = (await cur_t.fetchone())["id"]
        else:
            tool_id = tool_row["id"]

        # Insert run in Workspace A
        await db.execute(
            "INSERT INTO agent_runs (id, workspace_id, agent_id, input_text, status) VALUES (?, ?, ?, ?, ?)",
            (99091, ws_a, 1, "Trip valve", "paused")
        )

        # Create pending approval in Workspace A
        await db.execute(
            """INSERT INTO approval_requests 
               (id, run_id, tool_id, parameters, status)
               VALUES (?, ?, ?, ?, ?)""",
            (99091, 99091, tool_id, "{'valve': 'SV-401'}", "pending")
        )
        await db.commit()

        # Query pending approvals for Workspace B -> Must be 0
        cur_b_appr = await db.execute(
            """SELECT ar.* FROM approval_requests ar
               JOIN agent_runs r ON ar.run_id = r.id
               WHERE r.workspace_id = ? AND ar.status = 'pending'""",
            (ws_b,)
        )
        assert len(await cur_b_appr.fetchall()) == 0

        # Query pending approvals for Workspace A -> Must return approval #99091
        cur_a_appr = await db.execute(
            """SELECT ar.* FROM approval_requests ar
               JOIN agent_runs r ON ar.run_id = r.id
               WHERE r.workspace_id = ? AND ar.status = 'pending'""",
            (ws_a,)
        )
        a_rows = await cur_a_appr.fetchall()
        assert len(a_rows) == 1
        assert a_rows[0]["id"] == 99091
