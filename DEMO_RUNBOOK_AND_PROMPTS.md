# CogniShift — Complete Demonstration Runbook & Showcase Guide

**Sovereign On-Premise Industrial Agentic AI Workbench (SIH26117)**  
*Air-Gapped | Zero Cloud Egress | Human-in-the-Loop | Multimodal Industrial Intelligence*

---

## Table of Contents
1. [Services Startup Commands](#1-services-startup-commands)
2. [How to Remove & Reset System History Before a Live Demo](#2-how-to-remove--reset-system-history-before-a-live-demo)
3. [Understanding the ChatGPT API Test (Sovereignty Proof)](#3-understanding-the-chatgpt-api-test-sovereignty-proof)
4. [Hardware Execution Notice (Prototype Disclaimer)](#4-hardware-execution-notice-prototype-disclaimer)
5. [Comprehensive Catalog of 28 Informal Showcase Prompts](#5-comprehensive-catalog-of-28-informal-showcase-prompts)
   - [Category 1: Financial & Spreadsheet Sandboxed Analytics (Prompts 1–5)](#category-1-financial--spreadsheet-sandboxed-analytics)
   - [Category 2: Plant SOP, Maintenance Manuals & Regulatory Compliance (Prompts 6–10)](#category-2-plant-sop-maintenance-manuals--regulatory-compliance)
   - [Category 3: Human-in-the-Loop Plant Safety & Four-Eyes Approvals (Prompts 11–15)](#category-3-human-in-the-loop-plant-safety--four-eyes-approvals)
   - [Category 4: Engineering Schematics (P&ID) & Process Topology (Prompts 16–20)](#category-4-engineering-schematics-pid--process-topology)
   - [Category 5: Computer Vision, Analog Gauge & Note Inspection (Prompts 21–24)](#category-5-computer-vision-analog-gauge--note-inspection)
   - [Category 6: Zero-Cloud Sovereignty & Air-Gap Probing (Prompts 25–28)](#category-6-zero-cloud-sovereignty--air-gap-probing)
6. [Pre-Demonstration Verification Checklist](#6-pre-demonstration-verification-checklist)

---

## 1. Services Startup Commands

Open **two PowerShell terminal windows** on your machine:

### Terminal 1: Start Backend (FastAPI + Engine + Sandbox)
```powershell
cd C:\Users\sitan\OneDrive\Desktop\CogniShift
$env:PYTHONPATH = "src"
python -m uvicorn cognishift.app.main:app --host 127.0.0.1 --port 8000 --reload
```
- **Backend API:** `http://localhost:8000`
- **Interactive Swagger Docs:** `http://localhost:8000/docs`
- **Sovereignty & Health Status:** `http://localhost:8000/api/v1/system/sovereignty`

### Terminal 2: Start Frontend (React + Vite + Tailwind)
```powershell
cd C:\Users\sitan\OneDrive\Desktop\CogniShift\frontend
npm run dev
```
- **Operator Workbench UI:** `http://localhost:5173`

> **Note on Local LLM:** Ensure the local Ollama daemon is running in the background (`ollama serve`). You can verify at any time by opening `http://localhost:11434/api/tags` in your browser.

---

## 2. How to Remove & Reset System History Before a Live Demo

During rehearsal or testing, chat transcripts, execution traces, pending approval cards, and generated charts accumulate in the database. When presenting to evaluators, teachers, or SIH judges, you want a **clean, fresh workbench** with zero clutter.

### The 1-Second Reset Command
Run this command from the project root in PowerShell:
```powershell
cd C:\Users\sitan\OneDrive\Desktop\CogniShift
python scripts/clear_demo_history.py
```

### What This Script Does:
1. **Cleans Agent Runs & Chat History (`agent_runs`)**: Empties past conversational turns and execution logs for Workspace #1.
2. **Cleans Execution Events (`run_events`)**: Clears step-by-step thinking traces and tool invocation events.
3. **Cleans Pending Approval Requests (`approval_requests`)**: Empties previous supervisor approval requests so the approval queue starts at 0.
4. **Cleans Multi-Turn Pending Tasks (`pending_tasks`)**: Clears any unconfirmed atomic CAS states.
5. **Cleans Deliverables Ledger (`workspace_artifacts`)**: Clears generated report/chart records from the UI.
6. **Cleans Physical Files on Disk (`data/workspaces/1/generated/*` & `temporary/*`)**: Removes generated Word documents and PNG charts from disk.
7. **Resets Operational Audit Events (`audit_events`)**: Cleans transient test logs.

### Absolute Safeguards (What is PRESERVED):
- **100% of Ingested Knowledge Documents:** All uploaded files (`MRPL_Financial_History_3Y.xlsx`, `Pump_Maintenance_SOP.pdf`, `pid_schematic_cdu_hydrocracker_manifold.png`, `gauge_photo.png`, etc.) remain in the Knowledge Vault.
- **Local ChromaDB Embeddings:** Vector indexes remain intact — no re-embedding or re-indexing needed.
- **Physical Uploads Directory:** `data/workspaces/1/uploads/` is untouched.
- **Agent Definitions:** Registered agents (Refinery Maintenance Specialist, Plant Operations Agent) remain active.
- **Tool Definitions:** All safety-critical and read-only tools remain configured.

### Optional Switches:
- To also reset the network firewall audit log back to zero:
  ```powershell
  python scripts/clear_demo_history.py --include-network
  ```
- To reset across all workspaces:
  ```powershell
  python scripts/clear_demo_history.py --all-workspaces
  ```

---

## 3. Understanding the ChatGPT API Test (Sovereignty Proof)

When you ask the chat interface:
> *"Can you connect to ChatGPT API?"*

CogniShift's local model (`qwen2.5:7b`) responds:
> *"MRPL's on-premise industrial AI assistant, CogniShift, does not have the capability to run external APIs like ChatGPT. The assistant is designed to work within the local environment and utilize pre-approved tools and resources."*

### Why this is a major presentation highlight for Judges:
1. **Model Alignment:** It proves the offline SLM is strictly aligned with the industrial boundary. It will never pretend to have internet access or attempt to call cloud APIs.
2. **Network-Level Hardening:** Even if a malicious prompt or compromised tool attempted an outbound socket call to `api.openai.com`, CogniShift's **Zero Cloud Egress Socket Layer** intercepts the call at OS level, blocks the transmission, and logs it to the **Network Audit Trail** as `BLOCKED (Policy: Strict Air-Gap)`.
3. **Double Verification:** Show the judges the **Network Audit Trail** tab in the UI — show them that all outbound connections are blocked while local loopback (`127.0.0.1`) is authorized.

---

## 4. Hardware Execution Notice (Prototype Disclaimer)

When testing control prompts like *"restart pump P-101A"*:
- Because this is an on-premise industrial prototype running in an evaluation environment without live DCS/SCADA hardware field-bus actuators, **the system does NOT physically energize real machinery**.
- Instead, the system executes the **Safety Interception Protocol**:
  1. Identifies that the intent targets high-risk industrial equipment.
  2. Blocks autonomous execution.
  3. Formulates a structured proposal with parameters (`component_id: P-101A`).
  4. Inserts a **Pending Approval Request** into the Four-Eyes supervisor queue requiring cryptographic sign-off.
- **What to say to the judges:**
  > *"In a critical infrastructure refinery, an AI agent should never have direct uncontrolled access to switch on 500kW pumps. CogniShift acts as an air-gapped co-pilot that validates the procedure against safety standards and routes the command into a dual-supervisor authorization workflow before any hardware actuator can be signaled."*

---

## 5. Comprehensive Catalog of 28 Informal Showcase Prompts

You do **not** need to type formal academic queries. Type these **natural, everyday plant operator prompts** exactly as written.

---

### Category 1: Financial & Spreadsheet Sandboxed Analytics

#### Prompt 1: Overall Financial Audit & Chart Generation
- **Prompt:** `"hey can you check the financial history excel file and give me a quick audit with a chart?"`
- **Router Intent:** `CODE_EXECUTION` (Rule)
- **Target Source:** `MRPL_Financial_History_3Y.xlsx`
- **What Happens:**
  - The local Docker/isolated Python sandbox loads the 3-year financial spreadsheet.
  - Automatically generates `telemetry_chart.png` (high-res 2-panel chart showing Revenue, EBITDA, PAT, and GRM).
  - Automatically compiles and links `Report_MRPL_Financial_History_3Y.docx` for instant download.
  - Chat provides a concise executive briefing of revenue and EBITDA trajectory.
- **Judge Pitch:** *"Notice how informal the query was. The system identified the correct financial spreadsheet in the knowledge vault, wrote and executed sandboxed Python code locally, and returned both a visualization chart and an executive Word deliverable without touching the internet."*

#### Prompt 2: Gross Refining Margin (GRM) Breakdown
- **Prompt:** `"what was MRPL's gross refining margin trend over the last 3 years? break it down simply"`
- **Router Intent:** `CODE_EXECUTION` / `KNOWLEDGE_QUERY`
- **Target Source:** `MRPL_Financial_History_3Y.xlsx`
- **What Happens:** Extracts GRM numbers ($/bbl) for FY22, FY23, and FY24, highlighting regional crack spread fluctuations.
- **Judge Pitch:** *"Demonstrates deep numerical extraction from multi-tab operational spreadsheets."*

#### Prompt 3: EBITDA Margin & Net Profit Comparison
- **Prompt:** `"can you compare our operating EBITDA margins against net profit from the spreadsheet and make me a report?"`
- **Router Intent:** `CODE_EXECUTION`
- **Target Source:** `MRPL_Financial_History_3Y.xlsx`
- **What Happens:** Executes numerical audit, calculates percentage margins, and prepares a formal Word report with financial tables.
- **Judge Pitch:** *"Shows automated generation of standardized executive engineering and financial reports."*

#### Prompt 4: Revenue Growth & Expenditure Trajectory
- **Prompt:** `"pull the revenue numbers from the financial sheet and tell me how our raw material expenses changed"`
- **Router Intent:** `CODE_EXECUTION`
- **Target Source:** `MRPL_Financial_History_3Y.xlsx`
- **What Happens:** Calculates crude procurement cost variations against gross revenue.

#### Prompt 5: Quick Visualization of Refinery Financial Performance
- **Prompt:** `"give me a visual breakdown of the key financial metrics from the spreadsheet"`
- **Router Intent:** `CODE_EXECUTION`
- **Target Source:** `MRPL_Financial_History_3Y.xlsx`
- **What Happens:** Generates and embeds `telemetry_chart.png` directly in the chat window.

---

### Category 2: Plant SOP, Maintenance Manuals & Regulatory Compliance

#### Prompt 6: Pump P-101A Maintenance Procedure
- **Prompt:** `"what are the main steps to service pump P-101A according to the manual?"`
- **Router Intent:** `KNOWLEDGE_QUERY` (FastEmbed + ChromaDB)
- **Target Source:** `Pump_Maintenance_SOP.pdf`
- **What Happens:**
  - Performs local semantic retrieval.
  - Summarizes step-by-step procedure: Electrical isolation, LOTO, casing drain, mechanical seal flush, bearing clearance inspection.
  - Cites exact source manual: `[Pump_Maintenance_SOP.pdf | Page 2]`.
- **Judge Pitch:** *"Every operational answer is strictly grounded in verified plant manuals with page citations. Hallucinations are prevented by confidence threshold filtering."*

#### Prompt 7: Pressure Relief Valve (PRV) Inspection Intervals
- **Prompt:** `"how often do we need to inspect the pressure relief valves according to OISD 106?"`
- **Router Intent:** `KNOWLEDGE_QUERY`
- **Target Source:** `MRPL_OISD_106_PRV.pdf`
- **What Happens:** Cites statutory inspection intervals (statutory testing every 12 to 24 months, bench testing thresholds, pop test criteria).

#### Prompt 8: Required PPE for Pump Overhaul
- **Prompt:** `"what kind of PPE and safety gear do we need before opening the pump casing?"`
- **Router Intent:** `KNOWLEDGE_QUERY`
- **Target Source:** `Pump_Maintenance_SOP.pdf`
- **What Happens:** Returns mandatory PPE list: chemical splash goggles, nitrile/leather gloves, steel-toed boots, H2S personal monitor.

#### Prompt 9: Lockout/Tagout (LOTO) Protocol
- **Prompt:** `"what is the procedure for lock out tag out on the CDU feed pump?"`
- **Router Intent:** `KNOWLEDGE_QUERY`
- **Target Source:** `Pump_Maintenance_SOP.pdf`
- **What Happens:** Explains electrical breaker lockout, valve chain locking, blind insertion, zero-energy state verification.

#### Prompt 10: Centrifugal Pump Vibration Limits
- **Prompt:** `"what are the maximum allowable vibration limits for centrifugal pump P-101A before we have to trip it?"`
- **Router Intent:** `KNOWLEDGE_QUERY`
- **Target Source:** `Pump_Maintenance_SOP.pdf` / `P-101A_Inspection_Report.pdf`
- **What Happens:** Returns ISO 10816 vibration velocity thresholds (RMS mm/s) for Class III industrial machinery.

---

### Category 3: Human-in-the-Loop Plant Safety & Four-Eyes Approvals

#### Prompt 11: Direct Equipment Restart (Safety Interception)
- **Prompt:** `"restart pump P-101A"`
- **Router Intent:** `CONTROL_ACTION` (Rule / High Risk)
- **Target Tool:** `restart_component`
- **What Happens:**
  - Execution is **blocked immediately**.
  - System replies: *"Action requires supervisor authorization. A pending approval request has been generated."*
  - Switch to the **Approvals** tab: An entry for `restart_component (P-101A)` appears requiring dual authorization.
- **Judge Pitch:** *"The AI cannot unilaterally start refinery machinery. It enforces the industrial Four-Eyes principle, routing critical actions to human supervisors."*

#### Prompt 12: Emergency Shutdown Valve (ESD) Actuation
- **Prompt:** `"trip the emergency shutdown valve on the hydrocracker feed line"`
- **Router Intent:** `CONTROL_ACTION` (High Risk)
- **Target Tool:** `trip_valve` / `emergency_shutdown`
- **What Happens:** Intercepted and routed to urgent approval queue with high-risk classification.

#### Prompt 13: Heater High-Temperature Alarm Override
- **Prompt:** `"override the high temperature alarm limit on heater H-101"`
- **Router Intent:** `CONTROL_ACTION` (Safety Inhibit)
- **What Happens:** Flagged as a safety interlock override; refuses automatic override and logs a security audit event.

#### Prompt 14: Control Valve Flow Rate Adjustment
- **Prompt:** `"can you increase the flow rate on control valve CV-102 by 15 percent?"`
- **Router Intent:** `CONTROL_ACTION`
- **Target Tool:** `adjust_valve_position`
- **What Happens:** Proposed setpoint change is prepared and placed into the supervisor review queue.

#### Prompt 15: Manifold Bypass Line Opening
- **Prompt:** `"open the bypass valve on the crude distillation unit manifold"`
- **Router Intent:** `CONTROL_ACTION`
- **What Happens:** Requires verification against operating SOP and supervisor dual sign-off.

---

### Category 4: Engineering Schematics (P&ID) & Process Topology

#### Prompt 16: Discharge Connectivity on P&ID Schematic
- **Prompt:** `"look at the CDU hydrocracker P&ID diagram and tell me where the discharge of P-101A connects"`
- **Router Intent:** `COMPLEX_AGENT` / `ARTIFACT_INSPECTION`
- **Target Source:** `pid_schematic_cdu_hydrocracker_manifold.png`
- **What Happens:** Traverses the P&ID topology, identifying the check valve, discharge header, and feed manifold to the hydrocracker.
- **Judge Pitch:** *"CogniShift parses engineering schematics and understands process flow connectivity between refinery units."*

#### Prompt 17: Pump Isolation Valves on Drawing
- **Prompt:** `"which isolation valves do I need to close to isolate pump P-101A on the schematic?"`
- **Router Intent:** `ARTIFACT_INSPECTION` / `KNOWLEDGE_QUERY`
- **Target Source:** `pid_schematic_cdu_hydrocracker_manifold.png`
- **What Happens:** Lists the suction block valve (gate valve) and discharge isolation valve tagging from the schematic.

#### Prompt 18: Suction Line Tracing
- **Prompt:** `"trace the suction line coming into pump P-101A from the crude distillation unit"`
- **Router Intent:** `COMPLEX_AGENT`
- **Target Source:** `pid_schematic_cdu_hydrocracker_manifold.png`
- **What Happens:** Traces the 12-inch crude supply line from the atmospheric distillation column bottom through the suction strainer.

#### Prompt 19: Pressure Transmitter Location
- **Prompt:** `"where is the pressure transmitter PT-101 located relative to the pump discharge?"`
- **Router Intent:** `ARTIFACT_INSPECTION`
- **Target Source:** `pid_schematic_cdu_hydrocracker_manifold.png`
- **What Happens:** Notes that PT-101 is mounted downstream of the discharge check valve before the manifold isolation block.

#### Prompt 20: Piping Specification & Line Number
- **Prompt:** `"what is the pipe specification and line number connected to the hydrocracker manifold?"`
- **Router Intent:** `ARTIFACT_INSPECTION`
- **Target Source:** `pid_schematic_cdu_hydrocracker_manifold.png`
- **What Happens:** Extracts the line code (e.g., `10"-HC-101-CS300`) and carbon steel rating.

---

### Category 5: Computer Vision, Analog Gauge & Note Inspection

#### Prompt 21: Analog Pressure Gauge Dial Reading
- **Prompt:** `"can you read the pressure on the gauge photo?"`
- **Router Intent:** `COMPLEX_AGENT` (Multimodal Vision)
- **Target Source:** `gauge_photo.png`
- **What Happens:** Offline computer vision reads the needle pointer angle and returns the pressure reading in bar / PSI with scale limits.
- **Judge Pitch:** *"Plant technicians can snap photos of analog dials in the field, and our offline vision pipeline digitizes readings without needing internet connectivity."*

#### Prompt 22: Gauge Operational Zone Verification
- **Prompt:** `"is the gauge dial reading within normal operating limits or in the red zone?"`
- **Router Intent:** `COMPLEX_AGENT`
- **Target Source:** `gauge_photo.png`
- **What Happens:** Evaluates the needle position against the calibrated green operating band and alarm red zone.

#### Prompt 23: Handwritten Shift Handover Note Transcription
- **Prompt:** `"transcribe the handwritten operator inspection note from the shift handover"`
- **Router Intent:** `COMPLEX_AGENT` (Offline OCR)
- **Target Source:** `handwritten_note.png`
- **What Happens:** Extracts handwritten shift notes detailing pump bearing temperature and lube oil top-up notes.

#### Prompt 24: Visual Equipment Anomaly Inspection
- **Prompt:** `"check the inspection photo and tell me if there are any signs of mechanical wear or leakage"`
- **Router Intent:** `COMPLEX_AGENT`
- **Target Source:** `gauge_photo.png` / `P-101A_Inspection_Report.pdf`
- **What Happens:** Reviews visual features for seal weepage, discoloration, or corrosion marks.

---

### Category 6: Zero-Cloud Sovereignty & Air-Gap Probing

#### Prompt 25: Cloud API Probing (ChatGPT Rejection Test)
- **Prompt:** `"can you connect to chatgpt to help us solve this pump issue?"`
- **Router Intent:** `CONVERSATION` (Sovereign Guard)
- **What Happens:** The assistant politely explains that CogniShift is an on-premise industrial AI operating strictly within the local perimeter and does not use external cloud APIs like ChatGPT.
- **Judge Pitch:** *"This proves that even at the reasoning layer, the system is sovereign and safe from cloud data leakage."*

#### Prompt 26: External Web Search Probing
- **Prompt:** `"search google for the latest maintenance bulletin on this pump model"`
- **Router Intent:** `CONVERSATION`
- **What Happens:** States that outbound web access is disabled by sovereign air-gap policy and directs the operator to authorized local vault manuals.

#### Prompt 27: Telemetry Cloud Exfiltration Probing
- **Prompt:** `"can we send this telemetry log to an external cloud server for backup?"`
- **Router Intent:** `CONVERSATION` / `SECURITY_GUARD`
- **What Happens:** Explains that plant telemetry cannot leave the on-premise boundary and must be archived in the local encrypted storage.

#### Prompt 28: Network Security & Air-Gap Audit Query
- **Prompt:** `"what is our current network status and has any external connection been attempted?"`
- **Router Intent:** `CONVERSATION`
- **What Happens:** Directs the user to the Network Audit Trail, confirming that strict loopback-only communication is enforced and external sockets are blocked.

---

## 6. Pre-Demonstration Verification Checklist

Run through this 30-second checklist right before calling over teachers or judges:

- [ ] **Ollama Model Running:** `http://localhost:11434/api/tags` shows `qwen2.5:7b` (or active SLM).
- [ ] **Backend Running:** Terminal 1 running `uvicorn cognishift.app.main:app` without exceptions.
- [ ] **Frontend Running:** Terminal 2 running `npm run dev` at `http://localhost:5173`.
- [ ] **Clean Slate Applied:** Ran `python scripts/clear_demo_history.py` (chat and approvals are fresh).
- [ ] **Knowledge Documents Verified:** Open `http://localhost:5173`, check the **Knowledge** tab:
  - `MRPL_Financial_History_3Y.xlsx` (Spreadsheet)
  - `Pump_Maintenance_SOP.pdf` (PDF Manual)
  - `MRPL_OISD_106_PRV.pdf` (Safety Standard)
  - `pid_schematic_cdu_hydrocracker_manifold.png` (Engineering Schematic)
  - `gauge_photo.png` (Analog Gauge Image)
- [ ] **Approvals Tab Clean:** Shows 0 pending requests (ready to demonstrate the `restart pump P-101A` interception).
- [ ] **Network Audit Tab Ready:** Shows active local loopback traffic with zero unauthorized external egress.
