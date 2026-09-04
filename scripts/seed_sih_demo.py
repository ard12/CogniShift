"""Seed Phase 7 Synthetic Demo Assets for CogniShift.

Creates synthetic demonstration documents, configures the SIH demonstration workspace,
registers tools, provisions deterministic local credentials, and indexes base SOP.
All refinery assets are explicitly demarcated as SIMULATION DATA / SYNTHETIC DEMO INPUT.

ABSOLUTE RULE: Zero pre-created completed runs, approvals, or deliverable artifacts.
Those must occur strictly through live user actions.
"""

import os
import sys
import json
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from cognishift.app.config import settings
from cognishift.app.core.auth import User, register_local_credential, save_credential_store

DB_PATH = settings.database_path
DEMO_DIR = ROOT_DIR / "data" / "demo"
DEMO_DIR.mkdir(parents=True, exist_ok=True)


def create_demo_documents():
    """Generate high-fidelity synthetic PDFs, CSV telemetry, and images."""
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont

    # 1. Pump_Maintenance_SOP.pdf
    sop_path = DEMO_DIR / "Pump_Maintenance_SOP.pdf"
    doc_sop = pymupdf.open()
    page1 = doc_sop.new_page(width=595, height=842)  # A4

    # Header & Watermark
    page1.insert_text((50, 45), "SIMULATION DATA // SYNTHETIC DEMO INPUT", fontsize=10, color=(0.6, 0.2, 0.2))
    page1.insert_text((50, 70), "MANGALORE REFINERY & PETROCHEMICALS LIMITED (MRPL)", fontsize=14, fontname="helv", color=(0.1, 0.2, 0.4))
    page1.insert_text((50, 90), "STANDARD OPERATING PROCEDURE: CENTRIFUGAL PUMPS (API 610)", fontsize=12, fontname="helv", color=(0.2, 0.2, 0.2))
    page1.draw_line((50, 100), (545, 100), color=(0.3, 0.4, 0.5), width=1.5)

    sop_body = """DOCUMENT CODE: MRPL-SOP-PUMP-610 | REVISION: 4.2 | UNIT: HYDROTREATER 01
EQUIPMENT SCOPE: Heavy Gasoil Centrifugal Booster Pumps (Tag: P-101A / P-101B)

1.0 NOMINAL OPERATING WINDOW
- Suction Pressure: 15.0 - 25.0 PSI
- Normal Discharge Pressure: 80.0 - 120.0 PSI
- Maximum Allowable Working Pressure (MAWP): 500.0 PSI
- Automatic Overpressure Trip Limit: 450.0 PSI
- Bearing Housing Operating Temperature: 50.0 - 70.0 deg C (Trip threshold: 95.0 deg C)
- Radial Shaft Vibration Limit: 4.5 mm/s RMS (Trip threshold: 7.0 mm/s RMS)

2.0 EMERGENCY INTERVENTION PROTOCOL (HIGH-RISK ACTION)
If discharge pressure exceeds 450.0 PSI or bearing temperatures breach 90.0 deg C:
1. Immediately isolate secondary bypass line.
2. Verify trip interlock armed status using plant diagnostic check.
3. If mechanical seal barrier differential has stabilized, initiate controlled component restart.
4. AUTHORIZED INTERVENTION TOOL: restart_component (Parameters: component="P-101A")

3.0 MANDATORY FOUR-EYES GOVERNANCE REQUIREMENT
Per Refinery Safety Level 3 guidelines:
Any automated or assisted execution of 'restart_component' or 'emergency_pressure_relief'
CANNOT be authorized by the requesting operator alone.
It requires TWO INDEPENDENT AUTHORIZATIONS:
- Stage 1: Shift Supervisor (Verification of interlock thresholds and field status).
- Stage 2: Plant Authorizer / Operations Manager (Final release of safety barrier).
"""
    page1.insert_textbox((50, 115, 545, 780), sop_body, fontsize=9.5, fontname="helv")
    doc_sop.save(str(sop_path))
    doc_sop.close()

    # 2. P-101A_Inspection_Report.pdf
    rep_path = DEMO_DIR / "P-101A_Inspection_Report.pdf"
    doc_rep = pymupdf.open()
    r_page1 = doc_rep.new_page(width=595, height=842)

    r_page1.insert_text((50, 45), "SIMULATION DATA // SYNTHETIC DEMO INPUT", fontsize=10, color=(0.6, 0.2, 0.2))
    r_page1.insert_text((50, 70), "MRPL OPERATIONAL SHIFT LOG & FIELD INSPECTION REPORT", fontsize=14, fontname="helv", color=(0.1, 0.2, 0.4))
    r_page1.insert_text((50, 90), "UNIT 01: HYDROTREATER BOOSTER SYSTEM | DATE: 2026-09-04", fontsize=11, fontname="helv", color=(0.3, 0.3, 0.3))
    r_page1.draw_line((50, 100), (545, 100), color=(0.3, 0.4, 0.5), width=1.5)

    rep_body = """SHIFT: Morning Shift (06:00 - 14:00 IST)
INSPECTING TECHNICIAN: Operator Sam (Field ID: OP-48291)
TARGET EQUIPMENT: P-101A Centrifugal Booster Pump

CRITICAL TELEMETRY OBSERVATIONS:
- Equipment Tag P-101A discharge pressure transmitter PT-101 reads: 492.5 PSI.
- Safe operating threshold: 80 - 120 PSI.
- CRITICAL TRIP LIMIT (450.0 PSI) EXCEEDED by 42.5 PSI.
- Bearing temperature transmitter TT-204 metal reading: 92.1 deg C (Alarm limit 85 C).
- Vibration accelerometer VT-301 reading: 7.8 mm/s RMS (Critical trip limit 7.0 mm/s).
- Mechanical Seal Plan 53A buffer pressure differential dropping rapidly.

FIELD FINDINGS & PRELIMINARY DIAGNOSIS:
Transient vapour lock / cavitation caused discharge valve stiction.
Automatic interlock tripped pump driver.
Pump casing currently depressurizing through auxiliary balance line.

RECOMMENDED OPERATIONAL ACTION:
Per MRPL-SOP-PUMP-610 Section 2.0:
Verify safety interlocks and execute controlled 'restart_component' under Four-Eyes supervisor authorization.
Do NOT attempt restart without independent Stage 1 and Stage 2 sign-off.
"""
    r_page1.insert_textbox((50, 115, 545, 780), rep_body, fontsize=9.5, fontname="helv")
    doc_rep.save(str(rep_path))
    doc_rep.close()

    # 3. equipment_readings.csv
    csv_path = DEMO_DIR / "equipment_readings.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("# SIMULATION DATA // SYNTHETIC DEMO INPUT\n")
        f.write("timestamp,tag_id,equipment,measurement,value,unit,status\n")
        f.write("2026-09-04T08:00:00,PT-101,P-101A,discharge_pressure,104.2,PSI,NORMAL\n")
        f.write("2026-09-04T08:00:15,TT-204,P-101A,bearing_temp,68.4,C,NORMAL\n")
        f.write("2026-09-04T08:00:30,VT-301,P-101A,vibration_rms,2.3,mm/s,NORMAL\n")
        f.write("2026-09-04T08:05:00,PT-101,P-101A,discharge_pressure,492.5,PSI,HIGH_ALARM\n")
        f.write("2026-09-04T08:05:15,TT-204,P-101A,bearing_temp,92.1,C,HIGH_ALARM\n")
        f.write("2026-09-04T08:05:30,VT-301,P-101A,vibration_rms,7.8,mm/s,CRITICAL_TRIP\n")

    # 4. gauge_photo.png (synthetic analog gauge dial)
    gauge_path = DEMO_DIR / "gauge_photo.png"
    img = Image.new("RGB", (400, 400), color=(20, 24, 30))
    draw = ImageDraw.Draw(img)
    draw.ellipse([(40, 40), (360, 360)], outline=(120, 140, 160), width=4, fill=(10, 14, 20))
    draw.ellipse([(60, 60), (340, 340)], outline=(60, 70, 80), width=2)
    # Dial markings
    draw.text((150, 120), "P-101A", fill=(200, 220, 240))
    draw.text((135, 140), "DISCHARGE PSI", fill=(140, 160, 180))
    draw.text((160, 260), "492.5 PSI", fill=(240, 80, 80))
    draw.text((100, 320), "SIMULATION GAUGE", fill=(100, 110, 120))
    # Needle pointing towards high overpressure (near top-right)
    draw.line([(200, 200), (310, 110)], fill=(240, 60, 60), width=4)
    draw.ellipse([(190, 190), (210, 210)], fill=(220, 220, 220))
    img.save(str(gauge_path))

    # 5. handwritten_note.png
    note_path = DEMO_DIR / "handwritten_note.png"
    n_img = Image.new("RGB", (500, 200), color=(245, 242, 230))
    n_draw = ImageDraw.Draw(n_img)
    n_draw.text((20, 20), "URGENT FIELD MEMO // SIMULATION DATA", fill=(180, 40, 40))
    n_draw.text((20, 60), "P-101A TRIP: Pressure 492.5 PSI (Limit 450).", fill=(20, 30, 80))
    n_draw.text((20, 95), "Bearing Temp 92.1 C. Vibration 7.8 mm/s.", fill=(20, 30, 80))
    n_draw.text((20, 130), "Execute restart under Four-Eyes permit. - Sam", fill=(20, 30, 80))
    n_img.save(str(note_path))

    print(f"  [OK] Synthetic demo documents created in: {DEMO_DIR}")


def bootstrap_auth():
    """Bootstrap deterministic credentials for offline demonstration."""
    store_path = settings.auth_store_path
    tokens = {
        "operator": "test-key-operator-48291",
        "supervisor": "test-key-supervisor-71024",
        "administrator": "test-key-admin-99015",
        "tenant2": "test-key-tenant2-10842"
    }

    register_local_credential(tokens["operator"], User(user_id="operator_sam", role="operator", allowed_workspace_ids=[1]))
    register_local_credential(tokens["supervisor"], User(user_id="supervisor_jane", role="supervisor", allowed_workspace_ids=[1, 2]))
    register_local_credential(tokens["administrator"], User(user_id="admin_rohit", role="administrator", allowed_workspace_ids=[1, 2, 3]))
    register_local_credential(tokens["tenant2"], User(user_id="operator_tenant2", role="operator", allowed_workspace_ids=[2]))

    save_credential_store(store_path)
    print(f"  [OK] Local demonstration credentials provisioned to: {store_path}")


def seed_database():
    """Configure Workspace #1 and ensure tool definitions."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Workspace #1
    c.execute("""
        INSERT OR REPLACE INTO workspaces (id, name, description, operating_mode)
        VALUES (1, 'MRPL Operations — SIMULATION', 'Mangalore Refinery and Petrochemicals Limited - Unit 01 Simulation Workspace', 'local')
    """)

    # Agent #1
    c.execute("""
        INSERT OR REPLACE INTO agent_definitions (
            id, workspace_id, name, description, system_instructions, model_name, status, allowed_tool_ids, approval_required
        ) VALUES (
            1, 1, 'Refinery Maintenance Specialist',
            'Autonomous plant reasoning specialist for petrochemical operations, equipment diagnostics, and safety interlocks.',
            'You are the MRPL Industrial Operations AI Specialist. Analyze equipment telemetry against plant SOPs. When overpressure or critical trip conditions occur (e.g. pressure > 450 PSI on P-101A), cite the relevant SOP and recommend executing the authorized tool restart_component. State that high-risk restart requires Four-Eyes supervisor authorization.',
            'llama3.2:3b', 'active', '[1, 2, 3, 4, 5, 6, 8, 15]', 1
        )
    """)

    # Tool definitions
    tools = [
        (1, "check_pressure", "Check Pressure Reading", "read_only", 0, "check_pressure"),
        (2, "check_temperature", "Check Temperature Reading", "read_only", 0, "check_temperature"),
        (3, "run_diagnostic", "Run Equipment Diagnostic", "low_risk", 0, "run_diagnostic"),
        (4, "emergency_pressure_relief", "Emergency Pressure Relief", "service_interrupting", 1, "emergency_pressure_relief"),
        (5, "restart_component", "Restart System Component", "sensitive", 1, "restart_component"),
        (6, "check_interlock_status", "Check Plant Interlock Status", "read_only", 0, "check_interlock_status"),
        (8, "generate_docx", "Generate DOCX Report", "read_only", 0, "generate_docx"),
        (15, "execute_code", "Isolated Python Code Sandbox", "sensitive", 0, "execute_code")
    ]
    for tid, name, desc, risk, req_app, ikey in tools:
        c.execute("""
            INSERT OR REPLACE INTO tool_definitions (id, name, description, risk_level, requires_approval, enabled, implementation_key)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (tid, name, desc, risk, req_app, ikey))

    conn.commit()
    conn.close()
    print("  [OK] SQLite Workspace #1, Agent #1, and Tool Definitions verified.")


async def index_base_sop():
    """Index the base Pump_Maintenance_SOP.pdf into ChromaDB for workspace #1."""
    from cognishift.core.document_processing.service import DocumentProcessingService
    sop_path = DEMO_DIR / "Pump_Maintenance_SOP.pdf"
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Check if SOP is already indexed
    c.execute("SELECT id FROM knowledge_sources WHERE workspace_id = 1 AND name = 'Pump_Maintenance_SOP.pdf'")
    row = c.fetchone()
    if row:
        source_id = row["id"]
    else:
        c.execute("""
            INSERT INTO knowledge_sources (workspace_id, name, source_type, original_filename, local_path, processing_status)
            VALUES (1, 'Pump_Maintenance_SOP.pdf', 'pdf', 'Pump_Maintenance_SOP.pdf', ?, 'processing')
        """, (str(sop_path),))
        conn.commit()
        source_id = c.lastrowid
    conn.close()

    service = DocumentProcessingService()
    res = await service.process_document(
        workspace_id=1,
        source_id=source_id,
        file_path=sop_path,
        filename="Pump_Maintenance_SOP.pdf"
    )
    print(f"  [OK] Base SOP indexed into ChromaDB (Source #{source_id}, {res.get('chunk_count', 0)} chunks).")


def main():
    print("============================================================")
    print("  SEEDING COGNISHIFT PHASE 7 OFFLINE DEMO FIXTURES")
    print("============================================================")
    create_demo_documents()
    bootstrap_auth()
    seed_database()

    import asyncio
    asyncio.run(index_base_sop())

    print("============================================================")
    print("  DEMO SEED COMPLETE (CLEAN SLATE: 0 RUNS, 0 APPROVALS)")
    print("============================================================")

if __name__ == "__main__":
    main()
