"""Seed Phase 7 Synthetic Demo Assets for CogniShift.

Creates synthetic demonstration documents, seeds the Artifact Vault,
registers Phase 7 tools, and configures the SIH demonstration workspace.
All refinery assets are explicitly demarcated as SYNTHETIC / SIMULATION DATA.
"""
import os
import sys
import sqlite3
import hashlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

DB_PATH = ROOT_DIR / "data" / "cognishift.db"
DEMO_DIR = ROOT_DIR / "data" / "demo"
DEMO_DIR.mkdir(parents=True, exist_ok=True)

def seed_demo_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Update Workspace #1 title to match SIH Operations
    c.execute("""
        UPDATE workspaces 
        SET name = 'MRPL Operations Workspace',
            description = 'Mangalore Refinery and Petrochemicals Limited - Unit 01 Simulation Workspace'
        WHERE id = 1
    """)

    # 2. Register check_interlock_status tool
    c.execute("""
        INSERT OR IGNORE INTO tool_definitions (name, description, risk_level, requires_approval, enabled, implementation_key)
        VALUES (
            'check_interlock_status',
            'Check active plant safety interlocks and trip thresholds for designated equipment',
            'read_only',
            0,
            1,
            'check_interlock_status'
        )
    """)

    # 3. Create synthetic demo files
    # A. CSV Telemetry
    csv_path = DEMO_DIR / "equipment_readings.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("timestamp,tag_id,equipment,measurement,value,unit,status\n")
        f.write("2026-09-04T14:30:00,PT-101,P-101A,discharge_pressure,104.2,PSI,NORMAL\n")
        f.write("2026-09-04T14:30:15,TT-204,P-101A,bearing_temp,68.4,C,NORMAL\n")
        f.write("2026-09-04T14:30:30,VT-301,P-101A,vibration_rms,2.3,mm/s,NORMAL\n")
        f.write("2026-09-04T14:31:00,PT-101,P-101A,discharge_pressure,492.5,PSI,HIGH_ALARM\n")
        f.write("2026-09-04T14:31:15,TT-204,P-101A,bearing_temp,92.1,C,HIGH_ALARM\n")
        f.write("2026-09-04T14:31:30,VT-301,P-101A,vibration_rms,7.8,mm/s,CRITICAL_TRIP\n")

    # B. Synthetic Inspection Report (Text/PDF content)
    report_txt_path = DEMO_DIR / "P-101A_Inspection_Report.txt"
    with open(report_txt_path, "w", encoding="utf-8") as f:
        f.write("====================================================\n")
        f.write("MANGALORE REFINERY & PETROCHEMICALS LIMITED (MRPL)\n")
        f.write("SIMULATION REPORT — P-101A CENTRIFUGAL BOOSTER PUMP\n")
        f.write("====================================================\n")
        f.write("Date: 2026-09-04 | Shift: Morning | Unit: Hydrotreater 01\n")
        f.write("Equipment Tag: P-101A | Service: Heavy Gasoil Booster\n")
        f.write("Observations:\n")
        f.write("- Discharge pressure fluctuating between 485 - 495 PSI\n")
        f.write("- API 610 safe operating limit: 80 - 120 PSI\n")
        f.write("- MAWP boundary: 500 PSI | Trip limit: 450 PSI\n")
        f.write("- Bearing housing metal temperature elevated at 92.1 deg C\n")
        f.write("- Radial vibration spectrum shows high 1X harmonics (7.8 mm/s)\n")
        f.write("- Mechanical seal Plan 53A buffer pressure differential dropping\n")
        f.write("RECOMMENDATION: Immediate thermal stabilization & controlled restart under permit.\n")

    # 4. Ensure physical generated directory exists for Workspace 1
    gen_dir = ROOT_DIR / "data" / "workspaces" / "1" / "generated" / "run_1"
    gen_dir.mkdir(parents=True, exist_ok=True)

    # 5. Create physical artifact files with known SHA-256 hashes
    art_pdf = gen_dir / "Analysis_Report_P-101A.pdf"
    if not art_pdf.exists():
        with open(art_pdf, "wb") as f:
            f.write(b"%PDF-1.4\n%CogniShift Phase 7 Verified Synthetic Analysis Report\n1 0 obj\n<< /Title (P-101A Maintenance Assessment) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n")

    art_yaml = gen_dir / "Maintenance_Plan_P-101A.yaml"
    if not art_yaml.exists():
        with open(art_yaml, "w", encoding="utf-8") as f:
            f.write("workflow: WF-20250522-000143\nequipment: P-101A\naction: restart_component\nstatus: verified\n")

    art_zip = gen_dir / "Evidence_Pack_P-101A.zip"
    if not art_zip.exists():
        with open(art_zip, "wb") as f:
            f.write(b"PK\x03\x04\x14\x00\x00\x00\x08\x00CogniShiftSyntheticEvidencePack\x00\x00")

    # 6. Seed workspace_artifacts table if not already present
    artifacts_to_seed = [
        ("Analysis_Report_P-101A.pdf", "pdf", "Analysis Report P-101A", "generated/run_1/Analysis_Report_P-101A.pdf", "7c3e1b0f52d4a9c6f8e2d3a6b9c7f0e3d1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"),
        ("Maintenance_Plan_P-101A.yaml", "yaml", "Maintenance Plan P-101A", "generated/run_1/Maintenance_Plan_P-101A.yaml", "9ae6c3b2f1d8e7c6b5a49382716f0e1d2c3b4a59687766554433221100ffeedd"),
        ("Evidence_Pack_P-101A.zip", "zip", "Evidence Pack P-101A", "generated/run_1/Evidence_Pack_P-101A.zip", "d4f7a6b5c3e2d1f09876543210fedcba1234567890abcdef1234567890abcdef")
    ]

    for fname, atype, title, rel_path, sha in artifacts_to_seed:
        existing = c.execute("SELECT id FROM workspace_artifacts WHERE filename = ? AND workspace_id = 1", (fname,)).fetchone()
        if not existing:
            c.execute("""
                INSERT INTO workspace_artifacts (workspace_id, run_id, filename, relative_path, artifact_type, title, description, file_size, sha256_hash, metadata)
                VALUES (1, 1, ?, ?, ?, ?, 'Synthetic SIH Demonstration Deliverable', 1024, ?, '{"source": "demo_seeder"}')
            """, (fname, rel_path, atype, title, sha))

    # 7. Seed pending approval request for restart_component if none exists
    pending_appr = c.execute("SELECT id FROM approval_requests WHERE status = 'pending' AND workspace_id = 1").fetchone() if 'workspace_id' in [col[1] for col in c.execute("PRAGMA table_info(approval_requests)").fetchall()] else c.execute("SELECT id FROM approval_requests WHERE status = 'pending'").fetchone()
    if not pending_appr:
        tool_row = c.execute("SELECT id FROM tool_definitions WHERE name = 'restart_component'").fetchone()
        tool_id = tool_row[0] if tool_row else 5
        c.execute("""
            INSERT INTO approval_requests (run_id, tool_id, status, request_reason, parameters, risk_level, requested_at)
            VALUES (1, ?, 'pending', 'Detected abnormal vibration (7.8 mm/s) & high temp (92 deg C). Requires motor breaker re-engagement permit.', '{"component_id": "P-101A"}', 'high_risk', CURRENT_TIMESTAMP)
        """, (tool_id,))

    conn.commit()
    conn.close()
    print("[OK] Phase 7 Synthetic Demonstration Data successfully seeded.")

if __name__ == "__main__":
    seed_demo_data()
