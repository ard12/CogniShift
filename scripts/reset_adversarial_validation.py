"""CogniShift Adversarial Validation Workspace Reset.

Strictly scoped to the dedicated simulation workspace:
'CogniShift Adversarial Validation — SIMULATION'

Guarantees:
1. Never modifies or deletes records from unrelated workspaces (e.g. Workspace 1: MRPL Refinery Operations).
2. Verifies ChromaDB isolation invariant: vector counts for all other workspaces before == after.
3. Supports --dry-run flag to inspect targeted deletions without altering database or disk.
"""

import argparse
import asyncio
import os
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from cognishift.app.config import settings
from cognishift.core.retriever import get_workspace_vector_count, purge_workspace_collection

SIMULATION_WS_NAME = "CogniShift Adversarial Validation — SIMULATION"
SIMULATION_DIR = ROOT_DIR / "data" / "adversarial_simulation"


def parse_args():
    parser = argparse.ArgumentParser(description="Safely reset adversarial validation simulation workspace.")
    parser.add_argument("--dry-run", action="store_true", help="Preview items that would be deleted without executing.")
    return parser.parse_args()


async def reset_adversarial_workspace(dry_run: bool = False):
    db_path = settings.database_path
    if not db_path.exists():
        print(f"[RESET] Database {db_path} does not exist. Nothing to reset.")
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Find simulation workspace
    cursor.execute("SELECT id, name FROM workspaces WHERE name = ?", (SIMULATION_WS_NAME,))
    ws_row = cursor.fetchone()

    # Query all other workspaces to verify isolation invariant
    cursor.execute("SELECT id, name FROM workspaces WHERE name != ?", (SIMULATION_WS_NAME,))
    other_workspaces = [dict(r) for r in cursor.fetchall()]

    counts_before = {}
    for ow in other_workspaces:
        counts_before[ow["id"]] = get_workspace_vector_count(ow["id"])

    if not ws_row:
        print(f"[RESET] Workspace '{SIMULATION_WS_NAME}' does not exist. Nothing to clean.")
        print(f"[INVARIANT] Unrelated workspaces vector counts verified: {counts_before}")
        conn.close()
        return 0

    ws_id = ws_row["id"]

    # Query items to delete
    cursor.execute("SELECT COUNT(*) as cnt FROM agent_runs WHERE workspace_id = ?", (ws_id,))
    runs_count = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM run_events
        WHERE run_id IN (SELECT id FROM agent_runs WHERE workspace_id = ?)
    """, (ws_id,))
    events_count = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM approval_requests
        WHERE run_id IN (SELECT id FROM agent_runs WHERE workspace_id = ?)
    """, (ws_id,))
    approvals_count = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM workspace_artifacts WHERE workspace_id = ?", (ws_id,))
    artifacts_count = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM knowledge_sources WHERE workspace_id = ?", (ws_id,))
    sources_count = cursor.fetchone()["cnt"]

    vector_count = get_workspace_vector_count(ws_id)

    mode_label = "DRY RUN" if dry_run else "LIVE EXECUTION"
    print(f"=== COGNISHIFT ADVERSARIAL RESET ({mode_label}) ===")
    print(f"Target Workspace: '{SIMULATION_WS_NAME}' (ID: {ws_id})")
    print(f"  - Agent Runs: {runs_count}")
    print(f"  - Run Events: {events_count}")
    print(f"  - Approval Requests: {approvals_count}")
    print(f"  - Workspace Artifacts: {artifacts_count}")
    print(f"  - Knowledge Sources: {sources_count}")
    print(f"  - ChromaDB Vector Chunks: {vector_count}")
    print(f"  - Physical Simulation Directory: {SIMULATION_DIR}")

    if dry_run:
        print("\n[DRY RUN COMPLETE] Zero database rows or disk files were modified.")
        conn.close()
        return 0

    # Live Deletion
    # 1. Approval requests
    cursor.execute("""
        DELETE FROM approval_requests
        WHERE run_id IN (SELECT id FROM agent_runs WHERE workspace_id = ?)
    """, (ws_id,))

    # 2. Run events
    cursor.execute("""
        DELETE FROM run_events
        WHERE run_id IN (SELECT id FROM agent_runs WHERE workspace_id = ?)
    """, (ws_id,))

    # 3. Agent runs
    cursor.execute("DELETE FROM agent_runs WHERE workspace_id = ?", (ws_id,))

    # 4. Workspace artifacts
    cursor.execute("DELETE FROM workspace_artifacts WHERE workspace_id = ?", (ws_id,))

    # 5. Knowledge sources
    cursor.execute("DELETE FROM knowledge_sources WHERE workspace_id = ?", (ws_id,))

    conn.commit()
    conn.close()

    # 6. Physical workspace files
    ws_disk_dir = settings.data_dir / "workspaces" / str(ws_id)
    if ws_disk_dir.exists():
        shutil.rmtree(ws_disk_dir, ignore_errors=True)
    if SIMULATION_DIR.exists():
        shutil.rmtree(SIMULATION_DIR, ignore_errors=True)

    # 7. Purge ChromaDB collection for this workspace
    purged_vectors = purge_workspace_collection(ws_id)

    # 8. Assert Chroma isolation invariant
    counts_after = {}
    for ow in other_workspaces:
        counts_after[ow["id"]] = get_workspace_vector_count(ow["id"])

    for ow_id in counts_before:
        if counts_before[ow_id] != counts_after[ow_id]:
            raise AssertionError(
                f"CRITICAL ISOLATION VIOLATION: Workspace {ow_id} vector count changed from "
                f"{counts_before[ow_id]} to {counts_after[ow_id]} during adversarial reset!"
            )

    print(f"\n[LIVE RESET COMPLETED] Successfully purged simulation workspace {ws_id}.")
    print(f"[INVARIANT VERIFIED] Unrelated workspaces ({len(other_workspaces)}) vector counts unchanged:")
    for ow in other_workspaces:
        print(f"  Workspace {ow['id']} ('{ow['name']}'): {counts_after[ow['id']]} chunks")

    return 0


# Alias for backward and runner compatibility
reset_adversarial_simulation = reset_adversarial_workspace


if __name__ == "__main__":
    args = parse_args()
    sys.exit(asyncio.run(reset_adversarial_workspace(dry_run=args.dry_run)))
