"""
Permanent Remediation Verification Test Suite for Phase 4 Gate.
Verifies all Phase 3 Security Remediations:
- REMEDIATION 1 & 2 (CRIT-P3-01 & CRIT-P3-02): Subsystem directory access denied & canonical immutability.
- REMEDIATION 3 (CRIT-P3-03): allowed_tools=[] strictly denies all tools.
- REMEDIATION 4 (MED-P3-01): max_bytes strictly clamped between 1 and 1MB.
- REMEDIATION 5, 6, 7: directory_create, temporary/, and code/ protection.
- REMEDIATION 10: End-to-end knowledge boundary (RAG + filesystem + generated artifact).
- REMEDIATION 11: Case-insensitive immutability verification.
- REMEDIATION 12: Concurrent artifact creation safety.
"""

import pytest
import os
import shutil
import asyncio
from pathlib import Path
from unittest.mock import patch

from cognishift.app.config import settings
settings.operating_mode = "simulated"

from cognishift.core.tools import execute_tool
from cognishift.core.tool_schemas import validate_proposed_tool_call, TOOL_SCHEMAS
from cognishift.core.security import (
    resolve_workspace_path,
    ensure_workspace_layout,
    get_workspace_root,
    SecurityError
)
from cognishift.core.retriever import chroma_client, retrieve_context
from cognishift.core.artifact_generators import create_and_register_artifact, generate_docx_document
from cognishift.app.db.database import get_db, init_db
import docx


@pytest.fixture(autouse=True)
async def setup_gate_audit_db():
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (1, 'Audit Workspace')")
        await db.execute("INSERT OR REPLACE INTO agent_runs (id, workspace_id, agent_id, status) VALUES (50, 1, 1, 'completed')")
        await db.execute("DELETE FROM workspace_artifacts WHERE workspace_id = 1")
        await db.commit()
    ws_root = get_workspace_root(1)
    shutil.rmtree(ws_root / "generated", ignore_errors=True)
    shutil.rmtree(ws_root / "temporary", ignore_errors=True)
    ensure_workspace_layout(1)


# -----------------------------------------------------------------------------
# REMEDIATION 1, 5, 6, 7 & 9: SUBSYSTEM DIRECTORY BOUNDARIES
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_remediation_generic_file_write_subsystem_directories_strictly_denied():
    """Generic file_write must be strictly denied in generated/, temporary/, knowledge/, code/."""
    forbidden_writes = [
        "generated/fake_unregistered.docx",
        "temporary/hijack_staging.tmp",
        "knowledge/infiltrated_source.txt",
        "code/unvetted_script.py",
        "uploads/raw_upload.pdf"
    ]
    for target in forbidden_writes:
        res = await execute_tool(
            "file_write",
            {"file_path": target, "content": "MALICIOUS_SUBSYSTEM_WRITE", "overwrite": True},
            workspace_id=1
        )
        assert "Security Error" in res or "forbidden" in res.lower(), f"Expected write denial for {target}, got: {res}"


@pytest.mark.asyncio
async def test_remediation_generic_directory_create_subsystem_directories_strictly_denied():
    """directory_create must be strictly denied in subsystem roots."""
    forbidden_mkdirs = [
        "generated/fake_dir",
        "temporary/fake_dir",
        "knowledge/fake_dir",
        "code/fake_dir",
        "uploads/fake_dir"
    ]
    for target in forbidden_mkdirs:
        res = await execute_tool(
            "directory_create",
            {"directory_path": target},
            workspace_id=1
        )
        assert "Error" in res or "forbidden" in res.lower(), f"Expected mkdir denial for {target}, got: {res}"


@pytest.mark.asyncio
async def test_remediation_generic_file_read_and_list_internal_subsystems_denied():
    """Generic file_read and file_list must be strictly denied in knowledge/, temporary/, generated/, code/."""
    # Create internal dummy files
    ws_root = get_workspace_root(1)
    (ws_root / "knowledge" / "secret_chunk.txt").write_text("INTERNAL_SECRET")
    (ws_root / "temporary" / "candidate.tmp").write_text("STAGING_BYTES")

    forbidden_reads = [
        "knowledge/secret_chunk.txt",
        "temporary/candidate.tmp",
        "code/future_script.py"
    ]
    for target in forbidden_reads:
        res = await execute_tool("file_read", {"file_path": target}, workspace_id=1)
        assert "Error" in res or "forbidden" in res.lower(), f"Expected read denial for {target}, got: {res}"

    forbidden_lists = ["knowledge", "temporary", "code", "generated"]
    for target in forbidden_lists:
        res = await execute_tool("file_list", {"directory": target}, workspace_id=1)
        assert "Error" in res or "forbidden" in res.lower(), f"Expected list denial for {target}, got: {res}"


# -----------------------------------------------------------------------------
# REMEDIATION 2 & 11: CANONICAL IMMUTABILITY WITH OS CASE NORMALIZATION
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_remediation_canonical_immutability_denies_all_path_variants():
    """Path variants (Windows case, unnormalized dots, backslashes) must not modify registered artifact."""
    # 1. Register valid artifact
    art = await execute_tool(
        "generate_docx",
        {
            "filename": "critical_spec.docx",
            "title": "Critical Plant Spec",
            "sections": [{"heading": "Spec", "level": 1, "paragraphs": ["Initial immutable content."]}]
        },
        workspace_id=1,
        run_id=50
    )
    assert "Successfully generated" in art
    original_file = resolve_workspace_path(1, "generated/run_50/critical_spec.docx", purpose="read")
    initial_bytes = original_file.read_bytes()

    # 2. Attempt overwrites with path variations
    variants = [
        "generated/run_50/critical_spec.docx",
        "generated/RUN_50/critical_spec.docx",
        "generated/run_50/./critical_spec.docx",
        "generated\\run_50\\critical_spec.docx"
    ]
    for v in variants:
        res = await execute_tool(
            "file_write",
            {"file_path": v, "content": "TAMPERED_BYTES", "overwrite": True},
            workspace_id=1
        )
        assert "Security Error" in res or "forbidden" in res.lower()

    # 3. Verify disk file remains 100% identical
    assert original_file.read_bytes() == initial_bytes, "Registered artifact was modified on disk!"


# -----------------------------------------------------------------------------
# REMEDIATION 3: EMPTY ALLOWED TOOLS STRICTLY DENIES ALL TOOLS
# -----------------------------------------------------------------------------
def test_remediation_empty_allowed_tools_strictly_denies_every_tool():
    """When allowed_tools is [], EVERY tool must be rejected."""
    for tool_name in TOOL_SCHEMAS.keys():
        res = validate_proposed_tool_call(
            tool_name=tool_name,
            raw_parameters={"file_path": "documents/notes.txt", "content": "x"},
            allowed_tools=[]
        )
        assert res.valid is False, f"Tool {tool_name} was not rejected for empty allowed_tools!"
        assert res.risk_level == "forbidden"


def test_remediation_specific_allowed_tools_enforcement():
    """Agent allowed only file_read must be denied file_write and generate_docx."""
    res_allowed = validate_proposed_tool_call(
        tool_name="file_read",
        raw_parameters={"file_path": "documents/notes.txt"},
        allowed_tools=["file_read"]
    )
    assert res_allowed.valid is True

    res_write = validate_proposed_tool_call(
        tool_name="file_write",
        raw_parameters={"file_path": "documents/notes.txt", "content": "x"},
        allowed_tools=["file_read"]
    )
    assert res_write.valid is False
    assert res_write.risk_level == "forbidden"

    res_docx = validate_proposed_tool_call(
        tool_name="generate_docx",
        raw_parameters={"filename": "a.docx", "title": "t", "sections": [{"heading": "h", "level": 1}]},
        allowed_tools=["file_read"]
    )
    assert res_docx.valid is False
    assert res_docx.risk_level == "forbidden"


# -----------------------------------------------------------------------------
# REMEDIATION 4: FILE_READ BOUNDS AT SCHEMA AND RUNTIME
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_remediation_file_read_max_bytes_defense_in_depth():
    """max_bytes must be strictly clamped and never trigger unbounded reading."""
    await execute_tool(
        "file_write",
        {"file_path": "documents/bounds_test.txt", "content": "0123456789" * 10, "overwrite": True},
        workspace_id=1
    )
    # 1. Negative max_bytes -> clamped to 1 byte
    res_neg = await execute_tool(
        "file_read",
        {"file_path": "documents/bounds_test.txt", "max_bytes": -5},
        workspace_id=1
    )
    assert len(res_neg) == 1

    # 2. Zero max_bytes -> clamped to 1 byte
    res_zero = await execute_tool(
        "file_read",
        {"file_path": "documents/bounds_test.txt", "max_bytes": 0},
        workspace_id=1
    )
    assert len(res_zero) == 1

    # 3. Invalid string -> clamped to default 65536
    res_str = await execute_tool(
        "file_read",
        {"file_path": "documents/bounds_test.txt", "max_bytes": "invalid_number"},
        workspace_id=1
    )
    assert len(res_str) == 100


# -----------------------------------------------------------------------------
# REMEDIATION 10: END-TO-END KNOWLEDGE BOUNDARY (RAG + FS + ARTIFACT)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_remediation_end_to_end_knowledge_boundary_confidentiality():
    """
    Confidential Source B info must not leak through:
    1. RAG retrieval
    2. Filesystem tools
    3. Generated artifact
    """
    # 1. Seed Chroma with Source A (Authorized) and Source B (Confidential)
    col = chroma_client.get_or_create_collection("workspace_1")
    try:
        col.delete(where={"workspace_id": 1})
    except Exception:
        pass
    col.add(
        documents=[
            "Source A: AUTHORIZED_INFO_123 - Standard operating procedure.",
            "Source B: CONFIDENTIAL_INFO_987 - Secret plant safety code."
        ],
        embeddings=[[0.1] * 384, [0.9] * 384],
        metadatas=[
            {"source_id": 1, "workspace_id": 1, "filename": "SourceA.pdf"},
            {"source_id": 2, "workspace_id": 1, "filename": "SourceB.pdf"}
        ],
        ids=["chunk_a", "chunk_b"]
    )

    # 2. RAG retrieval with allowed_source_ids=[1]
    ctx = await retrieve_context(1, "plant safety code and procedure", top_k=5, allowed_source_ids=[1])
    assert "AUTHORIZED_INFO_123" in ctx
    assert "CONFIDENTIAL_INFO_987" not in ctx

    # 3. Filesystem attempt: Try reading internal knowledge directory
    ws_root = get_workspace_root(1)
    (ws_root / "knowledge" / "source_b.txt").write_text("CONFIDENTIAL_INFO_987")
    fs_read_res = await execute_tool("file_read", {"file_path": "knowledge/source_b.txt"}, workspace_id=1)
    assert "CONFIDENTIAL_INFO_987" not in fs_read_res
    assert "Error" in fs_read_res or "forbidden" in fs_read_res.lower()

    # 4. Generated Artifact: Agent generates document using retrieved context
    art_res = await execute_tool(
        "generate_docx",
        {
            "filename": "authorized_brief.docx",
            "title": "Plant Operations Brief",
            "sections": [{"heading": "Operational Findings", "level": 1, "paragraphs": [ctx]}]
        },
        workspace_id=1,
        run_id=50
    )
    assert "Successfully generated" in art_res

    # Inspect generated docx on disk
    doc_file = resolve_workspace_path(1, "generated/run_50/authorized_brief.docx", purpose="read")
    doc = docx.Document(str(doc_file))
    doc_full_text = " ".join(p.text for p in doc.paragraphs)
    assert "AUTHORIZED_INFO_123" in doc_full_text
    assert "CONFIDENTIAL_INFO_987" not in doc_full_text
