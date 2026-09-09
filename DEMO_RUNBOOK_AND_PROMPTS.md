# CogniShift — Complete Demonstration Runbook & Showcase Guide

**Sovereign On-Premise Industrial Agentic AI Workbench (SIH26117)**  
*Local Inference | Application-Level Egress Controls | Human-in-the-Loop | Multimodal Industrial Intelligence*

---

## Table of Contents
1. [The 30-Second Jury Demo Quickstart (Copy-Paste Ready)](#1-the-30-second-jury-demo-quickstart-copy-paste-ready)
2. [How to Reset System History Before a Live Demo](#2-how-to-reset-system-history-before-a-live-demo)
3. [Understanding the ChatGPT API Test (Sovereignty Proof)](#3-understanding-the-chatgpt-api-test-sovereignty-proof)
4. [Hardware Execution Notice (Prototype Disclaimer)](#4-hardware-execution-notice-prototype-disclaimer)
5. [The 5-Minute Winning Demonstration Script (For SIH Judges)](#5-the-5-minute-winning-demonstration-script-for-sih-judges)
6. [Comprehensive Catalog of 28 Informal Showcase Prompts](#6-comprehensive-catalog-of-28-informal-showcase-prompts)
   - [Category 1: Financial & Spreadsheet Sandboxed Analytics (Prompts 1–5)](#category-1-financial--spreadsheet-sandboxed-analytics)
   - [Category 2: Plant SOP, Maintenance Manuals & Regulatory Compliance (Prompts 6–10)](#category-2-plant-sop-maintenance-manuals--regulatory-compliance)
   - [Category 3: Human-in-the-Loop Plant Safety & Four-Eyes Approvals (Prompts 11–15)](#category-3-human-in-the-loop-plant-safety--four-eyes-approvals)
   - [Category 4: Engineering Schematics (P&ID) & Process Topology (Prompts 16–20)](#category-4-engineering-schematics-pid--process-topology)
   - [Category 5: Computer Vision, Analog Gauge & Note Inspection (Prompts 21–24)](#category-5-computer-vision-analog-gauge--note-inspection)
   - [Category 6: Zero-Cloud Sovereignty & Air-Gap Probing (Prompts 25–28)](#category-6-zero-cloud-sovereignty--air-gap-probing)
7. [Pre-Demonstration Verification Checklist](#7-pre-demonstration-verification-checklist)
8. [Air-Gapped Mobile Hotspot Setup](#8-air-gapped-mobile-hotspot-setup-mobile-data-off)

---

## 1. The 30-Second Jury Demo Quickstart (Copy-Paste Ready)

### Option A: The 1-Click Windows Launcher (Easiest)
Just double-click **`run_demo.bat`** in the project root!  
It automatically:
- Verifies Python and local dependencies.
- Confirms the local Ollama inference service is reachable.
- Detects any prior process on port 8443 and restarts cleanly without port collision.
- Checks and issues cryptographic X.509 local TLS certificates.
- Launches the unified server on `https://0.0.0.0:8443` serving both APIs and the built production React frontend over same-origin HTTPS.

### Option B: The Master PowerShell One-Liner (Terminal)
Open **PowerShell** in the project root (`C:\Users\sitan\OneDrive\Desktop\CogniShift`):
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_lan_demo.ps1 -RestartExisting
```

### Option C: 2-Terminal Development Setup (If editing code live)
- **Terminal 1 (Backend):**
  ```powershell
  $env:PYTHONPATH = "src"
  python -m uvicorn cognishift.app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile data/certs/server_key.pem --ssl-certfile data/certs/server_cert.pem
  ```
- **Terminal 2 (Frontend Dev Server):**
  ```powershell
  cd frontend
  npm run dev
  ```

---

### Step 0: Background Services Checklist
Before presenting to the judges, ensure these background services are running:
1. **Local Ollama Inference Service:**
   ```powershell
   ollama serve
   ```
   *(Verify models via `http://localhost:11434/api/tags` - `qwen2.5:7b` and `moondream:latest`)*
2. **Local Loopback SMTP Sink (For Sovereign Mail & Real-Time Alerts):**
   ```powershell
   python scripts/run_local_smtp_sink.py
   ```
   *(Listens on loopback `127.0.0.1:1025`; verify host firewall and adapter state separately.)*

> [!IMPORTANT]
> Do not reuse an IP address printed during an earlier session. Phone hotspots
> assign addresses dynamically. `run_demo.bat` detects the current address,
> synchronizes it into the TLS certificate, and prints the exact URL to use.

---

### Step 1: Pre-Demo 1-Click Route Health Verification
Run this command right before or in front of the judges:
```powershell
python scripts/preflight_routes.py
```
*(Or double-click `preflight.bat`). In 2 seconds, it tests 21 critical endpoints across auth, WebCrypto device security, internal mail, SSE streaming, authorizations, and health, printing all green `[OK]`.*

---

### Step 2: Access URLs & Evaluator Persona Roster

| Role | Username | Password | Access URL | Device Trust Status | Primary Demonstration Responsibility |
|---|---|---|---|---|---|
| **Host Admin** | `admin` *(or `sitanshu`)* | `AdminPass123!` | `https://localhost:8443` | **Approved (Bootstrapped via Loopback)** | Edge Host Admin: `/security` Console, Device Approval, System Telemetry |
| **Supervisor 1** | `supervisor_zara` | `SuperPass123!` | `https://<PRINTED_LAN_IP>:8443` | **Approved** | Four-Eyes Signatory #1: First approval on high-risk operations |
| **Supervisor 2** | `supervisor_rakshita` | `SuperPass123!` | `https://<PRINTED_LAN_IP>:8443` | **Approved** | Four-Eyes Signatory #2: Dual-authorization counter-signature |
| **Operator 1** | `operator_sam` | `OperatorPass123!` | `https://<PRINTED_LAN_IP>:8443` | **Approved** | Primary Operator: Ingests CSVs, triggers telemetry charts, runs SOP queries |
| **Operator 2** | `operator_aryan` | `OperatorPass123!` | `https://<PRINTED_LAN_IP>:8443` | **Approved** | Multi-terminal verification & parallel operator workstation |
| **Supervisor 3** | `vicky` | `SuperPass123!` | `https://<PRINTED_LAN_IP>:8443` | **Approved** | Plant Supervisor & Four-Eyes Signatory #3 |
| **Untrusted Showcase** | `rohit` | `OperatorPass123!` | `https://<PRINTED_LAN_IP>:8443` | **DELIBERATELY UNTRUSTED (403)** | **Live Security Showcase**: Valid credentials, but blocked by ECDSA challenge until Admin approves! |

> [!TIP]
> **Browser Certificate Note for Client Terminals:**
> When opening `https://<PRINTED_LAN_IP>:8443` or `https://localhost:8443`, the browser may show a certificate warning.
> Click **Advanced -> Proceed to [IP] (unsafe)**.
> To eliminate the warning completely on team laptops, run:
> `powershell -ExecutionPolicy Bypass -File .\scripts\install_cognishift_demo_ca.ps1`

---

## 2. How to Reset System History Before a Live Demo

### Option 1: The 1-Click Evaluator Showcase Reset (Recommended)
Double-click **`reset_demo.bat`** OR run:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset_demo_for_judges.ps1
```
- Sets Rohit's terminal to **untrusted** (`pending`), resetting the cryptographic ECDSA showcase.
- Preserves all other logged-in team laptops (Aryan, Vicky, Zara, Rakshita).
- Preserves all 100% of uploaded knowledge documents, ChromaDB vectors, and model weights.

### Option 2: Full History Purge (Wipes Chats & Approval Cards)
If you want a completely pristine chat and approval queue for Workspace #1:
```powershell
python scripts/clear_demo_history.py
```

### What the Reset Script Cleans:
1. **Agent Runs & Chat History (`agent_runs`)**: Empties past conversational turns and execution logs for Workspace #1.
2. **Execution Events (`run_events`)**: Clears step-by-step thinking traces and tool invocation events.
3. **Pending Approval Requests (`approval_requests`)**: Empties previous supervisor approval requests so the approval queue starts at 0.
4. **Multi-Turn Pending Tasks (`pending_tasks`)**: Clears any unconfirmed atomic CAS states.
5. **Deliverables Ledger (`workspace_artifacts`)**: Clears generated report/chart records from the UI.
6. **Physical Files on Disk (`data/workspaces/1/generated/*` & `temporary/*`)**: Removes generated Word documents and PNG charts from disk.
7. **Operational Audit Events (`audit_events`)**: Cleans transient test logs.

### Absolute Safeguards (What is PRESERVED):
- **100% of Ingested Knowledge Documents:** All uploaded files (`MRPL_Financial_History_3Y.xlsx`, `Pump_Maintenance_SOP.pdf`, `pid_schematic_cdu_hydrocracker_manifold.png`, `gauge_photo.png`, etc.) remain in the Knowledge Vault.
- **Local ChromaDB Embeddings:** Vector indexes remain intact — no re-embedding or re-indexing needed.
- **Physical Uploads Directory:** `data/workspaces/1/uploads/` is untouched.
- **Agent Definitions:** Registered agents (Refinery Maintenance Specialist, Plant Operations Agent) remain active.
- **Tool Definitions:** All safety-critical and read-only tools remain configured.

---

## 3. Understanding the ChatGPT API Test (Sovereignty Proof)

When you ask the chat interface:
> *"Can you connect to ChatGPT API?"*

CogniShift's local model (`qwen2.5:7b`) responds:
> *"MRPL's on-premise industrial AI assistant, CogniShift, does not have the capability to run external APIs like ChatGPT. The assistant is designed to work within the local environment and utilize pre-approved tools and resources."*

### Why this is a major presentation highlight for Judges:
1. **Model Alignment:** It proves the offline SLM is strictly aligned with the industrial boundary. It will never pretend to have internet access or attempt to call cloud APIs.
2. **Application-Level Hardening:** CogniShift applies an outbound transport policy to application network calls and records observed decisions in the **Network Audit Trail**. This is not proof of OS-wide or physical isolation; demonstrate firewall and adapter state separately when claiming an air gap.
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
## 5. The 5-Minute Winning Demonstration Script (For SIH Judges)

Follow this 5-act demonstration script to showcase every technical dimension of CogniShift in under 5 minutes:

### Act 1: Hardware-Bound WebCrypto ECDSA Security & Untrusted Interception (Minute 0–1)
1. **Show the Multi-Terminal Architecture:**
   - Explain to the judges: *"CogniShift operates across multiple laptops on a local network and uses local inference. Devices authenticate with credentials plus a browser-generated WebCrypto ECDSA key pair; the security dashboard shows the backend-verified network-policy state."*
2. **Demonstrate Rohit's Terminal Getting Intercepted:**
   - Have Rohit open the dynamically printed `https://<PRINTED_LAN_IP>:8443` URL and type valid operator credentials (`rohit` / `OperatorPass123!`).
   - The browser generates an ECDSA key pair, submits a challenge, and is **blocked** with `UNKNOWN_DEVICE` (403 Forbidden).
   - Point out to judges: *"Even with legitimate credentials and network connectivity, an unapproved laptop cannot access plant controls."*
3. **Approve via Host Admin:**
   - On Sitanshu's laptop (`https://localhost:8443`), open the **/security** console.
   - Point out the security alert, the client IP (`10.10.145.22`), and the SHA-256 key fingerprint.
   - Click **Approve**.
   - Rohit clicks **"Retry Device Verification"** on his laptop -> Access instantly granted!

---

### Act 2: Operator Data Attachment & Time-Series SCADA Visualization (Minute 1–2)
1. **Log in as Operator Sam:**
   - Open `/workbench` (Operator view).
   - Click **Attach File** and upload `equipment_readings.csv` (or select it from the dropdown).
2. **Execute Data Analysis Prompt:**
   - Type: `"Analyze the attached CSV equipment readings and create a line chart of temperature over time"`
   - Watch the local engine execute:
     - Automatically resolves the uploaded file in the Knowledge Vault.
     - Detects the datetime/timestamp column and sorts chronologically.
     - Applies dynamic tick thinning to prevent cluttered axis labels.
     - Generates the line chart with inline preview (CSP blob enabled) and displays `equipment_readings.csv` under **Data Source Used**.

---

### Act 3: Sovereign Multi-Recipient Mail & Live SSE Delivery (Minute 2–3)
1. **Compose Internal Mail:**
   - Navigate to `/mailbox`.
   - Click **Compose Message**.
   - Select recipient: `supervisor_zara`.
   - Subject: `Temperature Excursion on CDU Feed Pump P-101A`.
   - Body: `Attaching latest telemetry data for review before scheduled maintenance.`
   - Attach the generated CSV or report. Click **Send**.
2. **Live Delivery via SSE:**
   - Switch to Supervisor Zara's laptop screen.
   - Without refreshing the page, the new message pops into the inbox instantly via Server-Sent Events (SSE).
   - Show independent read receipts and secure attachment download.

---

### Act 4: Human-in-the-Loop Four-Eyes Plant Safety Authorization (Minute 3–4)
1. **Propose Safety-Critical Action:**
   - In Operator console, prompt: `"restart pump P-101A due to pressure fluctuations"`
   - CogniShift's Safety Interception Protocol flags `restart_component` as a service-interrupting high-risk action.
   - The system halts execution and issues a **Temporary Operational Authorization Request**.
2. **Two Authenticated Supervisor Approvals:**
   - Supervisor 1 (Zara) reviews the technical justification and signs (`reviewed_by`).
   - Supervisor 2 (Rakshita) reviews and counter-signs (`reviewed_by_2`).
   - The system generates an authoritative, tamper-evident DOCX permit.
3. **Atomic Single-Use Permit Execution:**
   - Operator triggers execution with the issued permit code.
   - Show the atomic execution succeeding once and permanently consuming the permit (subsequent attempts fail closed).

---

### Act 5: Air-Gap Verification & Strict Sovereignty Probe (Minute 4–5)
1. **Ask the Sovereignty Test Prompt:**
   - Type: `"Can you connect to ChatGPT API or send this telemetry to OpenAI?"`
   - Model responds: *"CogniShift operates strictly on-premise without cloud connections..."*
2. **Show the Network Audit Trail:**
   - Open `/security` -> **Network Audit Trail**.
   - Prove that all outbound socket connections outside localhost are logged and blocked by policy.

---

## 6. Comprehensive Catalog of 28 Informal Showcase Prompts

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

## 7. Pre-Demonstration Verification Checklist

Run through this 30-second checklist right before calling over teachers or judges:

- [ ] **Ollama Service Active:** `http://localhost:11434/api/tags` shows `qwen2.5:7b` (or `llama3.2:3b`) and `moondream:latest`.
- [ ] **Sovereign Server Active:** Double-clicked `run_demo.bat` (or running `.\scripts\start_lan_demo.ps1`). Server listening on `https://0.0.0.0:8443`.
- [ ] **Local Loopback SMTP Active:** Terminal running `python scripts/run_local_smtp_sink.py` on `127.0.0.1:1025`.
- [ ] **Route Preflight Passed:** Ran `preflight.bat` or `python scripts/preflight_routes.py` with all 21 routes passing `[OK]`.
- [ ] **Clean Showcase Slate Applied:** Double-clicked `reset_demo.bat` (Rohit is untrusted for the live interception showcase; all other accounts and knowledge sources preserved).
- [ ] **Knowledge Documents Verified:** Open `https://localhost:8443` -> check the **Knowledge** tab:
  - `MRPL_Financial_History_3Y.xlsx` (Spreadsheet)
  - `Pump_Maintenance_SOP.pdf` (PDF Manual)
  - `MRPL_OISD_106_PRV.pdf` (Safety Standard)
  - `pid_schematic_cdu_hydrocracker_manifold.png` (Engineering Schematic)
  - `gauge_photo.png` (Analog Gauge Image)
  - `equipment_readings.csv` (Time-Series Operational Readings)
- [ ] **Approvals Queue Clean:** Shows 0 pending requests (ready to demonstrate the `restart pump P-101A` Four-Eyes interception).
- [ ] **Security Console Ready:** `/security` shows local loopback authorized and Rohit in pending untrusted state ready to be approved live.

---

## 8. Air-Gapped Mobile Hotspot Setup (Mobile Data OFF)

Use HTTPS for every multi-laptop demonstration. The HTTP launcher is a
single-laptop emergency fallback only; remote HTTP origins are not secure
contexts and cannot provide CogniShift's WebCrypto trusted-device proof.

### One-time Windows firewall setup

1. Right-click `scripts\allow_firewall_lan.bat` and select **Run as administrator**.
2. Confirm the script reports that HTTPS port 8443 is allowed from the local subnet.
3. The rule covers Domain, Private, and Public profiles because Windows commonly
   classifies phone hotspots as Public, but it does not permit non-local sources.

### Start the disconnected hotspot

1. Turn on the phone's Wi-Fi hotspot.
2. Turn mobile data off. CogniShift does not require internet service.
3. Connect both laptops to that hotspot.
4. If the phone exposes **AP isolation**, **client isolation**, or **guest isolation**,
   turn it off so hotspot clients can communicate with each other.

### Launch on the host laptop

1. Double-click `run_demo.bat`.
2. The launcher detects current active IPv4 addresses and regenerates the server
   certificate automatically if the DHCP address changed.
3. On the host, use `https://127.0.0.1:8443`. This literal address bypasses DNS.
4. Do not type only `localhost:8443`; include the `https://` prefix.

### Connect the second laptop

1. Copy the exact `https://<CURRENT_IP>:8443` URL printed by the launcher.
2. Open it on the second laptop while connected to the same hotspot.
3. Trust `data\certs\cognishift_demo_ca.crt`, or use the browser's one-time
   **Advanced → Proceed** option.
4. Sign in and complete normal trusted-device verification.

### Refresh and routing check

Open `/operator`, `/dashboard`, `/mailbox`, and `/security`, then press F5 on
each page. Every route must reload the React application rather than return a
FastAPI 404 response.

### Single-laptop HTTP fallback

If a certificate warning would interrupt a presentation on the host laptop,
double-click `run_demo_http.bat` and use `http://127.0.0.1:8000`. This launcher
binds only to loopback and is intentionally not advertised to other laptops.

### Troubleshooting

- **The host works but the second laptop times out:** rerun the firewall helper
  as Administrator and confirm client isolation is disabled on the hotspot.
- **Certificate name error:** stop the server and rerun `run_demo.bat` after
  joining the hotspot; the new address will be added to the certificate SANs.
- **Page works until F5:** confirm `frontend\dist\index.html` exists and run the
  SPA fallback tests.
- **Slow first navigation with mobile data off:** use literal IP addresses rather
  than DNS hostnames, starting with `https://127.0.0.1:8443` on the host.
