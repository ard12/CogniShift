# CogniShift — SIH Offline / Air-Gap-Oriented Demonstration Runbook
**Document Version:** 3.0.0 (Validated Local Authentication and Workflow Baseline)  
**Target Event:** Smart India Hackathon (SIH26117) — Live Jury Walkthrough  
**Theme:** Sovereign On-Premise Agentic AI Workbench for Industrial Operations  
**Security Posture:** Strict Local Runtime / Air-Gap-Oriented / Zero Cloud Dependencies

---

## 1. System Requirements & Daemon Preflight

Before starting the evaluation, ensure that all required local background daemons are active.

### Step 1: Confirm Ollama Local Inference Service
Open PowerShell or Command Prompt:
```powershell
ollama list
```
**Expected Output:**
- `llama3.2:3b` (Text model, ~2.0 GB)
- `moondream:latest` (Vision model, ~1.7 GB)

If Ollama is not running, start it:
```powershell
ollama serve
```

### Step 2: Confirm Docker Container Runtime
Verify the local Docker daemon is running and the hardened sandbox image is present:
```powershell
docker images cognishift/sandbox-python:3.12-v1
```
**Expected Output:** `cognishift/sandbox-python:3.12-v1` listed with local Image ID.

---

## 2. Air-Gap / Network Disconnection Procedure

CogniShift is designed and verified to operate with external network interfaces disabled.

### Recommended Evaluation Sequence:
1. **Option A: Physical Air-Gap Disconnect (True Offline Demo)**
   - Disable Wi-Fi on the laptop:
     ```powershell
     netsh interface set interface "Wi-Fi" disable
     ```
   - Unplug any Ethernet cable.
   - Confirm external network isolation.
2. **Option B: Connected with Kernel Firewall Enforcement**
   - If Wi-Fi remains enabled, CogniShift's host security guard will block all outbound non-loopback connections and log any unauthorized external egress attempts in the audit ledger.

---

## 3. Preflight Readiness Verification

Run the automated offline preflight test suite from the repository root:

```powershell
cd C:\Users\sitan\OneDrive\Desktop\CogniShift
python scripts/check_offline_demo_readiness.py
```

**Expected Result (12/12 Checks Passing):**
```text
============================================================
  COGNISHIFT OFFLINE DEMO PREFLIGHT CHECKER
  Mode: 100% Offline / Zero Cloud / Zero Auto-Download
============================================================
  [OK] SQLite Database                     (15 tables initialized)
  [OK] ChromaDB Vector Store               (data/chroma)
  [OK] FastEmbed Model Cache               (bge-small-en-v1.5 onnx verified)
  [OK] RapidOCR Local Engine               (ONNX Runtime model weights ready)
  [OK] Ollama Local Service                (http://localhost:11434)
  [OK] LLM (llama3.2:3b)                   (Found)
  [OK] VLM (moondream:latest)              (Found)
  [OK] Docker Sandbox Image                (cognishift/sandbox-python:3.12-v1 present locally)
  [OK] Demo Credentials Store              (Operator, Supervisor, Administrator present)
  [OK] Frontend Static Assets              (Local index.html, app.css & app.js verified)
  [OK] Auth Store Configuration            (server and bootstrap store match)
  [OK] Local Demo Auth Capability          (installed; disabled by default)
  [OK] Synthetic Demo Documents            (data/demo)
  [OK] Demo Workspace (ID #1)              ('MRPL Operations — SIMULATION' configured)
============================================================
RESULT: READY FOR OFFLINE DEMO
All local models, services, images, and documents are 100% provisioned.
============================================================
```

---

## 4. Pristine State Seeding

Reset any prior run artifacts and populate the synthetic demo files:

```powershell
# Reset previous demo runs and deliverables (preserves system configuration & models)
python scripts/reset_sih_demo.py

# Seed clean workspace #1 fixtures and base SOP into ChromaDB
python scripts/seed_sih_demo.py
```

---

## 5. Launch the Operations Console

Start the FastAPI application on `127.0.0.1:8000`:

```powershell
$env:COGNISHIFT_DEMO_MODE='true'
python -m uvicorn cognishift.app.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Select Sam, Jane, or Rohit in the local authentication screen. These buttons request short-lived, process-memory sessions and are rejected when demo mode is disabled or the client is not loopback. Manual bearer authentication remains under the Advanced section.

Open Google Chrome or Edge and navigate to:
**`http://127.0.0.1:8000/`** (redirects to the Secure Industrial Operations Console)

---

## 6. Live 5-Minute Jury Demonstration Walkthrough

### Act I: Proving Local Sovereignty & Physical Network Status (Minute 0–1)
1. **Inspect Header Security Telemetry:**
   - Note the top status badges:
     - `STRICT MODE` (Active, green pulse)
     - `LOCAL ONLY` (Zero cloud APIs)
     - `PUBLIC EGRESS BLOCKED` (Host kernel enforcement)
     - `EXTERNAL NETWORK`: Displays `DISCONNECTED (AIR-GAP VERIFIED)` if Wi-Fi is off, or `CONNECTED (ACTIVE)` with outbound egress blocked.
2. **Inspect Left Navigation & Active Session:**
   - Active user profile in the top-right shows `operator_sam (ROLE: OPERATOR)` or `admin_rohit (ROLE: ADMIN)`.
   - Click the user avatar to switch personas dynamically.

### Act II: Document Ingestion & Local RapidOCR Extraction (Minute 1–2)
1. **Navigate to `Documents` Tab:**
   - View the base indexed manual: `Pump_Maintenance_SOP.pdf` (Type: `PDF`, Engine: `RapidOCR / PyMuPDF (Local)`, Status: `COMPLETED`).
   - Click **Pages & Provenance**: View real extracted pages, character confidence scores, and text excerpts stored locally in SQLite (`document_pages` table).
2. **Ingest a New Synthetic Inspection Sheet:**
   - Click "Browse" under the Upload dropzone and select `data/demo/P-101A_Inspection_Report.pdf` (or `handwritten_note.png`).
   - Click **INGEST LOCALLY**.
   - Watch the local pipeline execute:
     - PyMuPDF rasterizes pages
     - RapidOCR performs local character detection on CPU/GPU
     - FastEmbed embeds chunks locally into ChromaDB
     - Terminal console logs: `[INGEST] Indexed 'P-101A_Inspection_Report.pdf' with 4 chunks into ChromaDB`.

### Act III: Operational Reasoning & Four-Eyes Interlock Trigger (Minute 2–3)
1. **Navigate to `Dashboard` Tab:**
   - In the **Activity Console** prompt input at the bottom, type:
     ```text
     Analyze P-101A telemetry and evaluate overpressure against our pump maintenance SOP
     ```
   - Press **Enter** or click `>`.
2. **Observe Real Backend Execution:**
   - Real events stream into the Activity Console:
     - `[ROUTER]` Autonomous classification: `technical_reasoning` routed to `llama3.2:3b`.
     - `[RAG]` Retrieved `Pump_Maintenance_SOP.pdf | Page 2` (MAWP 500 PSI, Trip limit 450 PSI).
     - `[REASON]` Evaluates discharge pressure (492.5 PSI) exceeding safe boundary (450 PSI).
     - `[POLICY]` Proposes high-risk tool call: `restart_component`.
   - The **Workflow Stepper** pauses at step **6 SAFETY INTERLOCK (FOUR-EYES)**.
   - The **Approval Console** card lights up: `RISK: HIGH | INTERLOCK PENDING`.

### Act IV: Strict Four-Eyes Separation of Duties (Minute 3–4)
1. **Test Operator Unauthorized Attempt:**
   - Ensure active persona is **Operator (Sam)**.
   - Click **Review Request** in the Approval Console card.
   - Click **✓ AUTHORIZE ACTION**.
   - **Result:** System displays `403 FORBIDDEN: Role 'operator' is not authorized to approve high-risk actions. Only 'supervisor' or 'admin' may authorize.`
   - Console logs: `[HITL-DENIED] 403 Forbidden`.
2. **Stage 1 Verification (Supervisor):**
   - Click the profile switcher in the top right and select **Supervisor (Jane)**.
   - Click **Review Request**. Notice signer is now `supervisor_jane (SUPERVISOR)`.
   - Click **✓ AUTHORIZE ACTION**.
   - **Result:** Stage 1 is verified! The modal closes, console logs:
     `[HITL] Stage 1/2 Verified by supervisor_jane. Awaiting independent Stage 2 Authorizer sign-off.`
   - Dashboard Approval visualizer shows `Approver 1: VERIFIED (supervisor_jane)` and `Approver 2: STAGE 2 PENDING`.
   - The engine run remains safely **paused** (does NOT resume prematurely).
3. **Stage 2 Final Authorization (Plant Authorizer / Admin):**
   - Click the profile switcher and select **Admin (Rohit)**.
   - Click **Review Request**.
   - Click **✓ AUTHORIZE ACTION**.
   - **Result:** Four-Eyes dual approval complete! Console logs:
     `[HITL] Stage 2/2 Authorization complete (admin_rohit). High-risk execution resumed!`
   - Tool `restart_component` executes.
   - Stepper advances to step **7 ACTION** then step **8 DELIVERABLE**.

### Act V: Cryptographic Artifact Verification & Docker Sandbox (Minute 4–5)
1. **Inspect Artifact Vault:**
   - In the **Artifact Vault** on the Dashboard, view the newly minted deliverable:
     `Approval_Note_P101A.docx` (Type: `DOCX`, Status: `VERIFIED`).
   - Click the Preview icon (👁) to inspect the SHA-256 cryptographic hash.
   - Click the Download icon (📥): file downloads directly to the evaluator's browser.
2. **Docker Hardened Sandbox Execution:**
   - Navigate to `Sandbox` on the Left Navigation.
   - Click **EXECUTE IN ISOLATED CONTAINER**.
   - The local Docker daemon runs `cognishift/sandbox-python:3.12-v1` with `--network=none`, `--read-only`, and memory constraints.
   - Inspect container stdout: reads `equipment_readings.csv`, isolates 3-sigma anomalies, and generates `processed_equipment_readings.csv` with zero network egress.
3. **Network Sovereignty Audit Screen:**
   - Navigate to `Sovereignty` on the Left Navigation.
   - Point to the **Physical Network State** and **Kernel Network Policy** cards.
   - Review the ledger showing blocked external attempts (e.g. `api.openai.com:443 [BLOCKED]`).

---

## 7. Post-Demo Reset

To return the system to pristine condition for the next jury presentation:

```powershell
python scripts/reset_sih_demo.py
```
This cleans demo runs, approval requests, and generated artifacts in under 2 seconds without wiping base system models or configurations.
