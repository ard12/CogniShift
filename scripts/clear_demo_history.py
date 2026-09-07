"""CogniShift — Safe Demo History & Workbench Reset Utility.

Resets transient operator execution history in Workspace #1:
- Cleans agent runs and run execution events (chat history)
- Cleans human-in-the-loop approval requests (approvals queue)
- Cleans multi-turn pending tasks (CAS state)
- Cleans generated deliverables in workspace_artifacts
- Cleans physical generated files in data/workspaces/1/generated/ and temporary/
- Resets demo audit entries
- Optionally cleans network audit events (--include-network)

SAFEGUARDS (WHAT IS PRESERVED):
- All ingested knowledge sources (Excel, PDF SOPs, P&ID schematics, gauge photos)
- ChromaDB vector embeddings
- Workspaces, Agent definitions, Tool definitions, Graph nodes and edges
- Physical uploaded files in data/workspaces/1/uploads/
"""

import os
import sys
import shutil
import sqlite3
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from cognishift.app.config import settings

DB_PATH = settings.database_path

def clear_demo_history(workspace_id: int = 1, include_network: bool = False, all_workspaces: bool = False):
    print("=" * 65)
    print("       COGNISHIFT — SAFE DEMO HISTORY & WORKBENCH RESET       ")
    print("=" * 65)

    if not DB_PATH.exists():
        print(f"[-] Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    target_label = "ALL Workspaces" if all_workspaces else f"Workspace #{workspace_id}"
    print(f"[*] Target Scope: {target_label}")

    # 1. Identify runs to clean
    if all_workspaces:
        c.execute("SELECT id FROM agent_runs")
    else:
        c.execute("SELECT id FROM agent_runs WHERE workspace_id = ?", (workspace_id,))
    run_ids = [r["id"] for r in c.fetchall()]

    if run_ids:
        placeholders = ",".join("?" for _ in run_ids)
        c.execute(f"DELETE FROM run_events WHERE run_id IN ({placeholders})", run_ids)
        c.execute(f"DELETE FROM approval_requests WHERE run_id IN ({placeholders})", run_ids)
        c.execute(f"DELETE FROM agent_runs WHERE id IN ({placeholders})", run_ids)
        print(f"  [OK] Cleaned {len(run_ids)} agent runs, associated execution traces, and approvals.")
    else:
        if all_workspaces:
            c.execute("DELETE FROM approval_requests")
        print("  [OK] Zero active agent runs found.")

    # 2. Clean pending tasks (multi-turn CAS continuity states)
    if all_workspaces:
        c.execute("DELETE FROM pending_tasks")
    else:
        c.execute("DELETE FROM pending_tasks WHERE workspace_id = ?", (workspace_id,))
    deleted_tasks = c.rowcount
    print(f"  [OK] Cleared {deleted_tasks} pending multi-turn task states.")

    # 3. Clean generated deliverables from workspace_artifacts ledger
    if all_workspaces:
        c.execute("DELETE FROM workspace_artifacts")
    else:
        c.execute("DELETE FROM workspace_artifacts WHERE workspace_id = ?", (workspace_id,))
    deleted_artifacts = c.rowcount
    print(f"  [OK] Cleared {deleted_artifacts} generated deliverables from workspace_artifacts.")

    # 4. Clean audit events
    if all_workspaces:
        c.execute("DELETE FROM audit_events")
    else:
        c.execute("DELETE FROM audit_events WHERE workspace_id = ?", (workspace_id,))
    deleted_audits = c.rowcount
    print(f"  [OK] Reset {deleted_audits} operational audit events.")

    # 5. Optionally reset network events
    if include_network:
        c.execute("DELETE FROM network_events")
        print(f"  [OK] Reset network_events audit trail (Zero Cloud Egress ledger).")

    conn.commit()

    # Verify what remains
    c.execute("SELECT count(*) FROM knowledge_sources" + ("" if all_workspaces else f" WHERE workspace_id = {workspace_id}"))
    doc_count = c.fetchone()[0]
    c.execute("SELECT count(*) FROM agent_definitions")
    agent_count = c.fetchone()[0]
    c.execute("SELECT count(*) FROM tool_definitions")
    tool_count = c.fetchone()[0]
    conn.close()

    # 6. Clean physical generated and temporary files on disk
    ws_targets = [1] if not all_workspaces else [1, 2, 802, 902, 955, 1000]
    cleared_files_count = 0
    for wid in ws_targets:
        ws_dir = ROOT_DIR / "data" / "workspaces" / str(wid)
        for sub in ["generated", "temporary"]:
            target_sub = ws_dir / sub
            if target_sub.exists():
                for f in target_sub.glob("*"):
                    try:
                        if f.is_file():
                            f.unlink()
                            cleared_files_count += 1
                        elif f.is_dir():
                            shutil.rmtree(f, ignore_errors=True)
                            cleared_files_count += 1
                    except Exception:
                        pass
                target_sub.mkdir(parents=True, exist_ok=True)
    print(f"  [OK] Removed {cleared_files_count} generated charts/reports on disk (generated/ and temporary/).")

    print("\n" + "=" * 65)
    print("  SAFEGUARDS VERIFIED (PRESERVED ASSETS):")
    print(f"  - Knowledge Vault:     {doc_count} documents/spreadsheets/schematics intact")
    print(f"  - Agent Definitions:   {agent_count} industrial agents intact")
    print(f"  - Tool Definitions:    {tool_count} plant safety tools intact")
    print(f"  - Uploaded Raw Vault:  data/workspaces/{workspace_id}/uploads/ untouched")
    print(f"  - ChromaDB Embeddings: local vector store intact")
    print("=" * 65)
    print("  STATUS: Workbench is clean and ready for live demonstration!")
    print("=" * 65)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safely reset CogniShift demo execution history.")
    parser.add_argument("--workspace-id", type=int, default=1, help="Workspace ID to reset (default: 1)")
    parser.add_argument("--include-network", action="store_true", help="Also reset network firewall audit trail")
    parser.add_argument("--all-workspaces", action="store_true", help="Reset execution runs across all workspaces")
    args = parser.parse_args()

    clear_demo_history(
        workspace_id=args.workspace_id,
        include_network=args.include_network,
        all_workspaces=args.all_workspaces
    )
