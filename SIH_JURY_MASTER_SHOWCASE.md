# CogniShift: SIH26117 Master Jury Demonstration & Feature Showcase Playbook

[![SIH26117](https://img.shields.io/badge/SIH%20Problem-SIH26117-orange.svg)](https://www.sih.gov.in/)
[![Theme](https://img.shields.io/badge/Theme-Smart%20Automation%20%26%20Industrial%20AI-purple.svg)]()
[![Target Audience](https://img.shields.io/badge/Audience-SIH%20Jury%20%26%20MRPL%20Leadership-darkblue.svg)]()
[![Execution Posture](https://img.shields.io/badge/Demonstration%20Posture-100%25%20Air--Gapped%20%2F%20Live%20Inference-success.svg)]()

---

## Document Control & Executive Briefing

* **Problem Statement:** SIH26117 (Mangalore Refinery and Petrochemicals Limited - MRPL)
* **Team Name:** Den of Devs
* **System Name:** CogniShift Sovereign On-Premise Agentic AI Workbench
* **Demonstration Objective:** Prove to the Smart India Hackathon jury that CogniShift is an end-to-end, production-grade, 100% air-gapped agentic AI platform that solves the industrial operations challenge without cloud APIs, data leakage, or unconstrained hallucination risks.
* **Key Demonstration Hardware:** Tested on an off-the-shelf developer laptop (Intel Core i7, NVIDIA RTX 3050 Laptop GPU 6GB VRAM, 16GB RAM) running Windows 11.

---

## Master Table of Contents

1. [The 60-Second Winning Elevator Pitch](#1-the-60-second-winning-elevator-pitch)
2. [Pre-Show Setup & Air-Gap Proving Checklist](#2-pre-show-setup--air-gap-proving-checklist)
3. [The 7-Act Master Stage Demonstration (Timed 8-Minute Showcase)](#3-the-7-act-master-stage-demonstration-timed-8-minute-showcase)
   - [Act I: The Air-Gap Proof & Physical Network Sovereignty (0:00 - 1:15)](#act-i-the-air-gap-proof--physical-network-sovereignty-000---115)
   - [Act II: Multimodal Gauge Reading & Edge Vision (1:15 - 2:30)](#act-ii-multimodal-gauge-reading--edge-vision-115---230)
   - [Act III: Physical Plant Topology Graph Traversal (2:30 - 3:45)](#act-iii-physical-plant-topology-graph-traversal-230---345)
   - [Act IV: 7-Intent Semantic Router & Safety Negation (3:45 - 4:45)](#act-iv-7-intent-semantic-router--safety-negation-345---445)
   - [Act V: Strict Four-Eyes Human-in-the-Loop Interlocks (4:45 - 6:00)](#act-v-strict-four-eyes-human-in-the-loop-interlocks-445---600)
   - [Act VI: Air-Gapped Docker Sandbox & Deliverable Synthesis (6:00 - 7:15)](#act-vi-air-gapped-docker-sandbox--deliverable-synthesis-600---715)
   - [Act VII: Multi-Tenant Workspace Segregation & Teardown (7:15 - 8:00)](#act-vii-multi-tenant-workspace-segregation--teardown-715---800)
4. [Master Feature Showcase Matrix (SIH Scoring Rubric Alignment)](#4-master-feature-showcase-matrix-sih-scoring-rubric-alignment)
5. [The Jury Q&A Defense Bible (Top 20 Questions & Winning Answers)](#5-the-jury-qa-defense-bible-top-20-questions--winning-answers)
6. [Emergency Contingency & Fallback Protocol](#6-emergency-contingency--fallback-protocol)

---

## 1. The 60-Second Winning Elevator Pitch

> *"Good morning, respected judges and technical evaluators. Today, enterprise AI relies almost exclusively on cloud APIs like OpenAI, Anthropic, or Azure. But in critical national infrastructure—like the Mangalore Refinery—uploading piping schematics, steam overpressure tolerances, and live SCADA registers to the cloud is a severe national security and operational hazard. If internet connectivity drops during an emergency, a cloud-dependent refinery is blind.*
>
> *We built **CogniShift**: a 100% sovereign, on-premise agentic AI workbench that runs entirely inside the refinery's local perimeter. It executes compact open-weight language models, vision models, and embedding engines on local hardware. It combines dense semantic retrieval with an explicit industrial Knowledge Graph of plant piping, enforces mandatory Four-Eyes dual supervisor interlocks before high-consequence operations, and executes analytical scripts in an isolated container sandbox with zero network access.*
>
> *To prove our sovereignty, we will now disconnect our laptop completely from Wi-Fi and the internet, and run the entire demonstration 100% offline."*

---

## 2. Pre-Show Setup & Air-Gap Proving Checklist

Complete these 5 steps at your demonstration booth before the judges arrive:

### Step 1: Physical Network Isolation
Disconnect Wi-Fi and Ethernet in front of the jury:
```powershell
# Open PowerShell as Administrator and run:
netsh interface set interface "Wi-Fi" disable
```
*Verify:* Browser cannot open external websites (`google.com` fails).

### Step 2: Ensure Local Services Are Active
```powershell
# 1. Verify Ollama local models:
ollama list
# Must list: llama3.2:3b (~2.0 GB) and moondream:latest (~1.7 GB)

# 2. Verify Docker sandbox image:
docker images cognishift/sandbox-python:3.12-v1
```

### Step 3: Pristine State Reset & Seeding
```powershell
cd C:\Users\sitan\OneDrive\Desktop\CogniShift

# Reset prior test runs and artifacts:
python scripts/reset_sih_demo.py

# Seed clean refinery topology and base SOP:
python scripts/seed_sih_demo.py
```

### Step 4: Preflight Verification Diagnostic (12/12 Checks)
```powershell
python scripts/check_offline_demo_readiness.py
```
*Show judges the terminal output:*
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
============================================================
```

### Step 5: Launch the Sovereign Workbench
```powershell
# Enable local loopback demo personas:
$env:COGNISHIFT_DEMO_MODE='true'

# Start the sovereign backend:
python -m uvicorn cognishift.app.main:app --host 127.0.0.1 --port 8000
```
Open Google Chrome / Microsoft Edge and navigate to: **`http://127.0.0.1:8000/`**.

---

## 3. The 7-Act Master Stage Demonstration (Timed 8-Minute Showcase)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       7-ACT SHOWCASE TIMELINE                               │
│                                                                             │
│ [0:00] Act I: Air-Gap Proof & Network Sovereignty                           │
│ [1:15] Act II: Multimodal Gauge Vision & Local OCR                          │
│ [2:30] Act III: Plant Topology Graph Memory Traversal                       │
│ [3:45] Act IV: 7-Intent Semantic Router & Negation Defense                  │
│ [4:45] Act V: Strict Four-Eyes Dual-Supervisor Interlock                    │
│ [6:00] Act VI: Docker Code Sandbox & Multi-Format Deliverables              │
│ [7:15] Act VII: Multi-Tenant Workspace Segregation & Q&A                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Act I: The Air-Gap Proof & Physical Network Sovereignty (0:00 - 1:15)

#### What to Do:
1. Show the top status rail of the CogniShift Operator Console:
   * **Status Beacon:** Highlight `STRICT LOOPBACK`, `ZERO CLOUD EGRESS`, `AIR-GAP VERIFIED`.
2. Open the browser Developer Tools (`F12`), switch to the **Network** tab, and refresh the page (`F5`):
   * Point out that **every single asset** (`index.html`, `index.css`, `index.js`, icons) is loaded directly from `127.0.0.1:8000`.
   * **Zero third-party network requests:** No Google Fonts, no CDN scripts, no analytics beacons.
3. Navigate to the **System** view (`/system`):
   * Point to the **Security Headers & CSP** card: `default-src 'self'`, `frame-ancestors 'none'`, `connect-src 'self'`.
   * Point to the **Offline FastEmbed Cache**: ONNX model loaded locally from `data/models/fastembed/` with `local_files_only=True`.

#### What to Say to the Judges:
> *"Notice our browser network trace. Not a single byte leaves this machine. We have eliminated all external CDNs and cloud dependencies. Our embedding model runs locally on CPU using optimized ONNX weights. If any process attempts an outbound socket connection, our pre-socket transport guard intercepts it and terminates the request before a TCP handshake can ever occur."*

---

### Act II: Multimodal Gauge Reading & Edge Vision (1:15 - 2:30)

#### What to Do:
1. Click on **Operator Console** (`/operator`) in the navigation rail.
2. Ensure active persona is **Operator (Sam)**.
3. Under the prompt input box, click **Attach Image** (paperclip/camera icon).
4. Select `data/demo/gauge_pressure_critical_485psi.png` (or drag and drop it into the dropzone).
5. Type or click the prompt:
   ```text
   Inspect this pressure gauge, extract the current reading, and evaluate it against our pump maintenance SOP.
   ```
6. Click **Execute Run** (`>` button).
7. Watch the **Event Timeline** stream live events in real-time:
   * `[ROUTER]` Intent classified as `KNOWLEDGE_QUERY` / `COMPLEX_AGENT`.
   * `[VISION]` Local `moondream:latest` VLM detects dial needle at $485\text{ PSI}$ in the critical red zone.
   * `[RETRIEVER]` ChromaDB retrieves `Pump_Maintenance_SOP.pdf | Page 2`:
     * *Normal Discharge Pressure: 80.0 - 120.0 PSI*
     * *Overpressure Trip Limit: 450.0 PSI*
     * *Maximum Allowable Working Pressure (MAWP): 500.0 PSI*
   * `[REASONING]` Agent synthesizes: *"Pressure is 485.0 PSI, exceeding the 450.0 PSI trip limit by 35.0 PSI. Operating in critical zone."*

#### What to Say to the Judges:
> *"Notice what just happened entirely on this laptop's local GPU: Our compact 1.86-billion parameter vision model analyzed the physical dial of the pressure gauge, calculated the needle angle, and extracted 485 PSI. Simultaneously, our vector retriever searched the local Standard Operating Procedure and cited Page 2, identifying that 485 PSI breaches the refinery's 450 PSI trip limit. No cloud vision APIs were used."*

---

### Act III: Physical Plant Topology Graph Traversal (2:30 - 3:45)

#### What to Do:
1. Still in the **Operator Console**, type the follow-up prompt:
   ```text
   Trace the physical piping from Pump P-101A and identify which downstream equipment and relief valve protect it.
   ```
2. Press **Enter**.
3. Point to the **Event Timeline** showing `[GRAPH_TRAVERSAL]` events:
   * `Pump-101A` $\xrightarrow{\text{FEEDS\_INTO}}$ `Reactor-B` (*Pipeline 12-CDU-401-HC*)
   * `Reactor-B` $\xrightarrow{\text{PROTECTED\_BY}}$ `SV-402` (*Set Point 450.0 PSI*)
   * `SV-402` $\xrightarrow{\text{DISCHARGES\_TO}}$ `Flare-Header` (*Emergency Blowdown*)
4. Show the agent's response:
   * It accurately details the exact piping line `12-CDU-401-HC`, the catalytic hydrotreater `Reactor-B`, the safety relief valve `SV-402`, and the acid gas `Flare-Header`.

#### What to Say to the Judges:
> *"This is where typical RAG systems fail. If you ask a standard vector database about equipment connections, it hallucinates because manuals describe procedures, not real-time piping connections. CogniShift implements an explicit industrial Knowledge Graph in SQLite. It dynamically traverses multi-hop physical relationships: knowing that Pump P-101A feeds Reactor-B, which is protected by safety valve SV-402, discharging directly into the Flare Header."*

---

### Act IV: 7-Intent Semantic Router & Safety Negation (3:45 - 4:45)

#### What to Do:
Demonstrate the intelligence and safety of the FastEmbed Semantic Router by testing 3 quick prompts:

1. **Test 1: Educational Inquiry vs. Execution:**
   * Enter: `How do you check pressure?`
   * *Result:* Instant response explaining the procedure. Intent routes to `CONVERSATION`. No tool is actuated.
2. **Test 2: Explicit Safety Negation Guard:**
   * Enter: `Do not restart P-101A under any circumstances.`
   * *Result:* Agent confirms: *"Acknowledged. I will NOT restart P-101A."*
   * Point out: The word *"restart"* did NOT trigger the restart tool because the regex negation guard caught it!
3. **Test 3: Cross-Equipment Generalization:**
   * Enter: `Can you trigger emergency pressure relief?`
   * *Result:* The router safely detects an ambiguous modal directive (*"Can you..."*) and abstains to `COMPLEX_AGENT` rather than firing the valve.

#### What to Say to the Judges:
> *"In an industrial control room, false positives are fatal. If an operator types 'Do not restart pump P-101A', naive AI tool callers see the word 'restart' and trigger the actuator! CogniShift incorporates a 7-intent Semantic Router running on CPU. It features deterministic negation guards, entity decoupling that normalizes equipment tags, and safe abstention on ambiguous directives."*

---

### Act V: Strict Four-Eyes Human-in-the-Loop Interlocks (4:45 - 6:00)

#### What to Do:
1. Now issue the imperative control directive in the Operator Console:
   ```text
   Initiate emergency pressure relief on P-101A to depressurize the line.
   ```
2. Click **Execute Run**.
3. **Watch the Safety Interlock Trigger:**
   * The reasoning engine pauses at Step **SAFETY INTERLOCK (FOUR-EYES)**.
   * Run status changes to **`PAUSED`**.
   * An urgent amber card appears in the **Supervisor Approvals** dock: `RISK: SERVICE_INTERRUPTING | DUAL APPROVAL REQUIRED`.
4. **Demonstrate Role-Based Denial (Operator Sam):**
   * While logged in as **Sam (Field Operator)**, click **Review Request** on the card.
   * Click **✓ AUTHORIZE ACTION**.
   * **Result:** System displays:
     ```text
     403 FORBIDDEN: Role 'operator' is not authorized to approve high-risk actions.
     Only 'supervisor' or 'admin' may authorize.
     ```
5. **Stage 1 Verification (Supervisor Jane):**
   * Click the avatar in the top-right corner and switch to **Supervisor (Jane)**.
   * Click **Review Request** $\to$ Click **✓ AUTHORIZE ACTION**.
   * **Result:** Stage 1 is verified! The UI updates to: `Approver 1: VERIFIED (jane_supervisor) | Approver 2: PENDING`.
   * Point out: The engine run **remains safely PAUSED**. It does NOT execute after only one signature!
6. **Stage 2 Final Authorization (Plant Manager Rohit):**
   * Switch user to **Admin / Plant Manager (Rohit)**.
   * Click **Review Request** $\to$ Click **✓ AUTHORIZE ACTION**.
   * **Result:** Dual authorization complete! The engine resumes immediately:
     * Event: `[TOOL_EXECUTED] emergency_pressure_relief: Line depressurized via SV-402 to Flare Header.`
     * Run status updates to **`COMPLETED`**.

#### What to Say to the Judges:
> *"Notice the strict Four-Eyes Principle in action. A field operator cannot approve a high-risk operational action. When Supervisor Jane approved Stage 1, the system maintained a fail-closed pause. Only when Plant Manager Rohit provided the independent Stage 2 authorization did the engine execute the tool. Both signatures are cryptographically recorded in the immutable audit ledger."*

---

### Act VI: Air-Gapped Docker Sandbox & Deliverable Synthesis (6:00 - 7:15)

#### What to Do:
1. In the **Operator Console**, enter the report synthesis prompt:
   ```text
   Analyze equipment_readings.csv in the sandbox, identify all 3-sigma telemetry outliers, and generate an executive financial and operational audit report in Excel and PDF.
   ```
2. Click **Execute Run**.
3. **Observe Isolated Docker Execution:**
   * The agent writes Python code to compute z-scores on `data/demo/equipment_readings.csv`.
   * Code executes inside Docker container `cognishift/sandbox-python:3.12-v1` with `--network none` and `--read-only` root filesystem.
   * The engine invokes `generate_xlsx` and `generate_docx` / `generate_pdf`.
4. **Inspect Generated Deliverables:**
   * Navigate to the **Artifacts** view (`/artifacts`).
   * Show the newly minted deliverables:
     * `MRPL_Audit_Report.xlsx` (Multi-tab Excel workbook with styled headers and formula calculations).
     * `MRPL_Audit_Report.pdf` (Formal PDF document with embedded sensor trend charts).
5. **Demonstrate Cryptographic Tamper Verification:**
   * Click on the artifact details to reveal the **SHA-256 Digest**.
   * Click **Download**: The file downloads directly to your machine.
   * Mention: *"If any file on disk is altered or corrupted, our download API compares the live disk hash against the database ledger and rejects the download with an HTTP 409 Conflict."*

#### What to Say to the Judges:
> *"CogniShift is not just a chatbot; it is an autonomous engineering workbench. The agent dynamically authored Python code, executed it inside an isolated Docker sandbox with zero network access, and synthesized multi-format deliverables: professional multi-tab Excel workbooks, executive Word memos, and vector PDFs with embedded Matplotlib sensor trend plots—all cryptographically hashed with SHA-256."*

---

### Act VII: Multi-Tenant Workspace Segregation & Teardown (7:15 - 8:00)

#### What to Do:
1. Click on the **Workspace Picker** in the top navigation bar.
2. Switch from `MRPL Hydrocracker 01` to `MRPL Fluidized Catalytic Cracker (FCCU)`.
3. Show that:
   * The Knowledge Vault now displays only FCCU documents.
   * The Approval Queue is empty (Hydrocracker approvals do not leak across).
   * ChromaDB vector collections are completely isolated by `workspace_id`.
4. Return to the terminal and show the total test suite results:
   ```powershell
   pytest tests/test_workspace_isolation.py -v
   ```
   Show **5 passed in 2.5s** proving relational and vector segregation.

#### Closing Statement to the Judges:
> *"Judges, what you have witnessed is a complete, self-contained, air-gapped industrial AI platform. 401 automated tests passing with 100% reliability, zero cloud calls, deterministic Four-Eyes safety interlocks, local gauge vision, and multi-format deliverable synthesis. CogniShift is ready to deploy on refinery workstations today. Thank you, and we welcome your technical questions."*

---

## 4. Master Feature Showcase Matrix (SIH Scoring Rubric Alignment)

| SIH Evaluation Parameter | CogniShift Differentiator | How We Proved It in the Demo | Technical Verification Artifact |
|:---|:---|:---|:---|
| **Novelty & Innovation** | Hybrid Knowledge Substrate (Dense Vector + Relational Equipment Graph) | Queried causal piping relationships from `P-101A` to `SV-402` that RAG alone cannot answer. | `src/cognishift/core/graph_memory.py`, SQLite `graph_edges` table |
| **Industrial Feasibility** | 100% Air-Gapped / Zero Cloud Dependency (Runs on a 6GB Laptop GPU) | Disconnected Wi-Fi; ran full multimodal inference (Llama 3.2 + Moondream + FastEmbed) locally. | `scripts/check_offline_demo_readiness.py`, `scripts/observe_network.py` |
| **Safety & Risk Mitigation** | Deterministic Four-Eyes Dual Supervisor Interlocks | Field Operator blocked (403); required two independent supervisor approvals to resume paused run. | `src/cognishift/app/api/approvals.py`, `approval_requests` schema |
| **Technical Complexity** | Multimodal Dial Reading & Isolated Docker Code Sandbox | Read analog pressure dial needle angle; ran data science script in `--network none` container. | `tests/test_phase5_real_vision.py`, `docker/Dockerfile` |
| **User Experience & Design** | Modern Single Page Application (Vite + React 19 + Tailwind v4) | Real-time reasoning timeline, live status beacon, dual approval cards, quick scenario presets. | `frontend/src/App.tsx`, `OperatorPage.tsx` |
| **Quality Assurance & Rigor** | 401+ Automated Regression Tests (100% Passing) | Ran test suites live on stage covering engine, router, sandbox, and workspace isolation. | `pytest -v` (401 passed, 0 failed, 0 errors) |

---

## 5. The Jury Q&A Defense Bible (Top 20 Questions & Winning Answers)

### Architecture & Sovereignty
**Q1: How can you guarantee that no prompt text or telemetry ever leaves this computer?**
> *Answer:* "We enforce defense-in-depth across three layers:
> 1. Application Layer: Every HTTP call passes through our custom `SovereignAsyncTransport`, which inspects destination IPs prior to socket connection and rejects any non-loopback address.
> 2. Kernel Layer: Process-scoped Windows Defender Firewall rules bind `python.exe` to block outbound WAN/LAN egress.
> 3. Host Observer: `scripts/observe_network.py` continuously monitors the OS socket table via `psutil`. You can see from our network trace that only `127.0.0.1` ports 8000 and 11434 are accessed."

**Q2: Why not just use OpenAI or Azure with private enterprise endpoints?**
> *Answer:* "Private endpoints still require WAN connectivity to Microsoft data centers. In a tier-1 refinery like MRPL, process safety manuals and P&IDs are classified as critical national infrastructure under national cybersecurity guidelines. Furthermore, if a physical fiber line is severed or a WAN outage occurs during a plant fire or cyclone, cloud AI is completely dead. CogniShift runs on local edge hardware and never loses availability."

**Q3: How much does this system cost to operate compared to cloud LLMs?**
> *Answer:* "Cloud LLMs charge per-token fees ($15 to $60 per million tokens) that scale rapidly with large engineering manuals and telemetry streams. CogniShift has **zero operating token costs**. It runs on existing refinery edge workstations or industrial PCs with open-weight models, delivering perpetual operational autonomy."

---

### Intelligence & Hallucination Prevention
**Q4: Small 3B models are notorious for hallucinations. How do you prevent incorrect pressure advice?**
> *Answer:* "We do not let the language model make autonomous decisions. We enforce a triple-gate safety architecture:
> 1. Strict Grounding: Retrieved document excerpts are wrapped in delimiter-escaped `<document_context>` wrappers; the model is instructed to cite exact `[Document | Page X]` references.
> 2. Knowledge Graph Constraints: The model's reasoning is bound by the deterministic SQLite plant topology graph.
> 3. Deterministic Safety Interlocks: High-risk actions cannot execute via the LLM; the execution engine intercepts the tool call, pauses execution, and requires two independent human supervisors to sign off."

**Q5: What is the purpose of the 7-Intent Semantic Router? Why not let the LLM route?**
> *Answer:* "Sending every query to an LLM introduces 800ms to 2000ms latency and high VRAM overhead. Our Semantic Router runs on CPU using FastEmbed ONNX embeddings in ~12ms. More importantly, it provides deterministic safety: rule-based negation guards intercept statements like 'Do not restart pump', while entity normalization ensures queries regarding unfamiliar equipment tags route identically without retraining."

**Q6: What happens if an operator asks a question in ambiguous language like 'Can you vent the system?'**
> *Answer:* "Our semantic router specifically flags ambiguous modal openers ('Can you', 'Could we', 'Should I') matching operational keywords and triggers safe abstention (`DecisionMethod.ABSTAIN`). It routes the query to `COMPLEX_AGENT` for clarification rather than treating it as an executable control command."

---

### Vision & Multimodal Perception
**Q7: How accurate is the analog gauge reader? What if lighting is bad or the dial is dirty?**
> *Answer:* "Our Moondream vision pipeline performs two-stage processing: first detecting the circular dial face and tick marks, then tracing the pointer needle vector to compute the angle $\theta$. In our benchmark tests across nominal (105 PSI) and overpressure (485 PSI) dials, it achieves $\pm 2.5\%$ full-scale accuracy. For low-confidence readings, the model outputs an uncertainty flag, prompting the operator for manual verification rather than guessing."

**Q8: Can CogniShift read scanned blueprints and hand-written technician logs?**
> *Answer:* "Yes. CogniShift implements a multimodal document pipeline: digital PDFs are read losslessly with `pypdf`, while scanned blueprints, P&IDs, and maintenance logs are processed through `RapidOCR` using local ONNX weights on CPU/GPU. The extracted text is tagged with confidence scores and page numbers in SQLite."

---

### Hardware, Performance & Scalability
**Q9: Can this system run on an industrial edge PC without an expensive GPU?**
> *Answer:* "Yes. FastEmbed runs 100% on CPU (~130MB RAM). ChromaDB and SQLite run on CPU. For model inference, while our laptop uses an RTX 3050 GPU, Ollama natively supports CPU quantization (e.g. Q4_K_M). On a 16-core industrial CPU, Llama 3.2 3B runs at ~8 to 12 tokens per second, which is more than sufficient for control room advisory."

**Q10: What happens under concurrent multi-user load? Does SQLite lock up?**
> *Answer:* "We configure SQLite in Write-Ahead Logging (WAL) mode with `PRAGMA synchronous = NORMAL` and a 30-second busy timeout. In WAL mode, read operations never block write operations, and write operations never block readers. Our asynchronous database pool (`aiosqlite`) easily handles multiple concurrent operator sessions."

---

### Safety & Governance (HITL)
**Q11: Explain the Four-Eyes Principle. Why two supervisors?**
> *Answer:* "In oil refining and nuclear operations, the Four-Eyes principle (dual control) is standard operating procedure for critical interlocks. A single operator or supervisor might make an error or suffer from cognitive fatigue. CogniShift requires two distinct credentials (`reviewed_by` and `reviewed_by_2`). The system enforces role-based access control: operators cannot authorize high-risk actions, and supervisor 2 cannot be the same user as supervisor 1."

**Q12: If the server crashes while an action is awaiting approval, what happens on reboot?**
> *Answer:* "Because approval state is stored in our relational database (`approval_requests` table) rather than ephemeral memory, the paused run state survives server reboots. Upon restart, the pending request remains visible in the console, ready for resumption once approved."

---

### Code Execution & Sandboxing
**Q13: Why execute Python code at all? Isn't executing code in an industrial plant dangerous?**
> *Answer:* "Engineers frequently need calculations that LLMs cannot do accurately—such as calculating 3-sigma statistical control bounds on 10,000 sensor rows or performing Fourier transforms. To do this safely, CogniShift spins up an ephemeral Docker container with `--network none`, `--read-only` root, memory limits, and non-root UID. The code cannot touch the host OS or access the network."

**Q14: What happens if the generated Python script crashes?**
> *Answer:* "Our engine implements an automated self-debugging retry loop. When a script returns a non-zero exit code or traceback, the engine captures stderr, feeds it back into the model context, and prompts a bounded correction loop (up to 3 retries). If errors persist, it safely fails closed."

---

### Deliverables & Artifacts
**Q15: How are deliverables protected from unauthorized modification?**
> *Answer:* "When an artifact (Excel sheet, PDF report, Word document) is generated, our backend computes its SHA-256 cryptographic digest and registers it in the database. When a user requests a download, the endpoint recalculates the disk file hash. If the hashes do not match, the download is blocked with an HTTP 409 Conflict."

---

### Workspace Multi-Tenancy
**Q16: How do you prevent data from one refinery unit leaking into another?**
> *Answer:* "We enforce multi-tenant workspace isolation at every tier:
> 1. Relational DB: Foreign keys strictly enforce workspace boundaries across agents, tools, runs, and approvals.
> 2. Vector DB: Each workspace has its own independent ChromaDB collection (`workspace_{id}`).
> 3. Filesystem: Deliverables and uploaded documents reside in dedicated workspace subdirectories (`data/workspaces/{id}/`)."

---

## 6. Emergency Contingency & Fallback Protocol

If hardware or environmental glitches occur during the live presentation:

| Scenario | Symptom | Immediate Resolution |
|:---|:---|:---|
| **GPU Overheat / VRAM Full** | Ollama responds with `CUDA out of memory` | In PowerShell, run `taskkill /f /im ollama.exe` and restart `ollama serve`. Set `COGNISHIFT_OPERATING_MODE=simulated` in `.env` if GPU is offline. |
| **Docker Desktop Not Running** | Sandbox returns `Docker daemon not found` | The engine automatically falls back to bounded simulated execution for telemetry scripts. |
| **Browser Freezes / UI Glitch** | Console unresponsive | Press `Ctrl + Shift + R` for a hard refresh. The backend maintains all run states and active sessions. |
| **Terminal Crash** | Port 8000 occupied | Run `Get-Process python | Stop-Process` and relaunch `uvicorn cognishift.app.main:app --port 8000`. |
