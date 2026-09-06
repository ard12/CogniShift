# CogniShift — Local Operations Runbook & Sovereign Deployment Guide

**Document Version:** 2026-09-05-v1  
**Classification:** Operational Runbook — On-Premise Sovereign Workbench  
**Applies To:** CogniShift Enterprise / SIH26117 On-Premise Agentic AI  

---

## 1. System Architecture & Zero-Cloud Sovereign Philosophy

CogniShift is an entirely sovereign, on-premise agentic AI workbench engineered for mission-critical industrial environments (e.g., refinery operations, power generation, and critical manufacturing).

```
                      +-------------------------------------------------+
                      |          Activity Console (Browser UI)          |
                      |          http://127.0.0.1:8000/                 |
                      +------------------------+------------------------+
                                               | HTTP / REST + Static
                                               v
+---------------------------------------------------------------------------------------+
|                                    CogniShift Backend                                 |
|                                                                                       |
|  +---------------------------+  +----------------------------+  +-------------------+ |
|  | Conversation Context      |  | Native Semantic Router     |  | Hardware-Aware    | |
|  | Resolver (Anaphora & Ref) |->| FastEmbed Cosine Router    |->| Model Router      | |
|  +---------------------------+  +----------------------------+  +-------------------+ |
|                                                                                       |
|  +---------------------------+  +----------------------------+  +-------------------+ |
|  | Local Ollama Provider     |  | Hybrid Knowledge Retrieval |  | Dynamic Workflow  | |
|  | Llama 3.2 3B / Moondream  |  | ChromaDB (D^2 <= 0.78)     |  | Stepper Engine    | |
|  +---------------------------+  +----------------------------+  +-------------------+ |
|                                                                                       |
|  +---------------------------+  +----------------------------+  +-------------------+ |
|  | Artifact Vault            |  | Docker Execution Sandbox   |  | Four-Eyes Dual    | |
|  | XLSX, DOCX, CSV, TSV, JSON|  | Air-Gapped (--network none)|  | Tool Authorization| |
|  +---------------------------+  +----------------------------+  +-------------------+ |
+---------------------------------------------------------------------------------------+
                                               |
         +-------------------------------------+---------------------------------+
         |                                     |                                 |
         v                                     v                                 v
+------------------+                 +--------------------+            +-------------------+
|  SQLite Database |                 | Chroma Vector Store|            | Local Filesystem  |
|  cognishift.db   |                 | data/chroma/       |            | data/workspaces/  |
+------------------+                 +--------------------+            +-------------------+
```

### Sovereign Invariants:
1. **Zero Cloud Telemetry & Zero External APIs:** The system operates 100% air-gapped without making outbound HTTP/HTTPS requests to OpenAI, Anthropic, Google, or any remote IP.
2. **Local Embedding & Inference:** All vector embeddings are generated locally via `fastembed` (BAAI/bge-small-en-v1.5) on CPU. All LLM and vision reasoning runs on local hardware via `Ollama`.
3. **Workspace Multi-Tenant Isolation:** Documents, artifacts, vector collections, and execution sandboxes are strictly isolated by `workspace_id`. Cross-workspace bleeding is prevented at the database, storage, and retriever layers.
4. **Deterministic Fail-Closed Grounding:** If evidence is missing from local documents or artifacts, the system deterministically replies with fail-closed notices rather than hallucinating external URLs, fake portals, or ungrounded procedures.

---

## 2. Prerequisites & Hardware Specifications

| Component | Minimum Specification | Recommended Production Specification |
|---|---|---|
| **Operating System** | Windows 10/11 (64-bit) or Linux x86_64 | Windows 11 Enterprise / Ubuntu 22.04 LTS |
| **Python** | Python 3.12.x | Python 3.12.x (with venv) |
| **RAM** | 16 GB DDR4/DDR5 | 32 GB DDR5 |
| **CPU** | 4-Core Intel Core i5 / AMD Ryzen 5 | 8-Core Intel Core i7 / AMD Ryzen 7 |
| **GPU (Optional)** | Integrated Graphics (Ollama on CPU) | NVIDIA RTX 3060 / 4060 (6GB+ VRAM) |
| **Disk Space** | 20 GB free SSD storage | 100 GB NVMe SSD |
| **Docker** | Docker Desktop with WSL2 (Windows) | Docker Engine 24.x+ |
| **Local LLM Server** | Ollama v0.3.x+ running on `http://127.0.0.1:11434` | Ollama v0.3.x+ with GPU acceleration |

---

## 3. Project Directory Structure & Sovereign Layout

```
CogniShift/
├── artifacts/                           # Verification reports and execution summaries
│   ├── adversarial_validation_report.json
│   └── semantic_router_generalization.json
├── data/                                # Local persistent runtime state (Excluded from Git)
│   ├── cognishift.db                    # Primary SQLite relational database (WAL mode)
│   ├── chroma/                          # ChromaDB vector store directory
│   ├── private/auth_store.json          # Salted password hashes & session tokens
│   ├── uploads/                         # Temporary upload staging
│   └── workspaces/                      # Workspace-scoped document and artifact roots
│       ├── 1/                           # Workspace 1: MRPL Refinery Operations
│       └── 1000/                        # Workspace 1000: Adversarial Simulation
├── docs/                                # Technical documentation, runbooks, and audit logs
│   ├── LOCAL_OPERATIONS_RUNBOOK.md      # This authoritative runbook
│   └── SYSTEM_AUDIT_2026-09-05.md       # Comprehensive verification audit
├── scripts/                             # Operational maintenance and benchmark runners
│   ├── reset_adversarial_validation.py  # Isolated safe reset runner (--dry-run)
│   ├── seed_adversarial_validation.py   # Multi-domain synthetic testbed generator
│   └── run_adversarial_validation.py    # 6-suite automated adversarial runner
├── src/cognishift/                      # Source code packages
│   ├── app/                             # FastAPI application layer, DB schemas, endpoints
│   │   ├── api/                         # REST API routers (runs, knowledge, approvals, etc.)
│   │   ├── core/auth.py                 # Multi-user RBAC and session token validator
│   │   ├── db/database.py               # Async aiosqlite connection manager
│   │   ├── db/models.py                 # Pydantic v2 data transfer schemas
│   │   ├── static/                      # Self-contained HTML5/CSS3/Vanilla JS Activity Console
│   │   └── config.py                    # Environment settings and distance thresholds
│   └── core/                            # Engine, routing, retrieval, sandbox, and context
│       ├── conversation_context.py      # Multi-turn reference & anaphora resolver
│       ├── semantic_router.py           # FastEmbed multi-domain intent router
│       ├── model_router.py              # Hardware-aware VRAM model selector
│       ├── retriever.py                 # ChromaDB distance-filtered vector search
│       ├── graph_memory.py              # Plant topology equipment-sensor graph
│       ├── engine.py                    # Central agent reasoning loop
│       └── tools.py                     # Safe simulated operational tool registry
└── tests/                               # Comprehensive automated regression suites
```

---

## 4. Environment Setup & Configuration

Create or update `.env` in the repository root:

```ini
# Runtime Operating Mode
OPERATING_MODE=local
LOG_LEVEL=INFO

# Local LLM Server (Ollama)
OLLAMA_BASE_URL=http://127.0.0.1:11434
TEXT_MODEL=llama3.2:3b
VISION_MODEL=moondream

# Semantic Router Configuration
SEMANTIC_ROUTER_ENABLED=true
SEMANTIC_ROUTER_CONFIDENCE_THRESHOLD=0.70
SEMANTIC_ROUTER_MARGIN_THRESHOLD=0.10
SEMANTIC_ROUTER_CONTROL_CONFIDENCE_THRESHOLD=0.75
SEMANTIC_ROUTER_CONTROL_MARGIN_THRESHOLD=0.12
SEMANTIC_ROUTER_MAX_HISTORY_TURNS=8

# Retrieval Vector Calibration (Squared L2 Distance Threshold)
SEMANTIC_RETRIEVAL_MAX_DISTANCE=0.78

# Sandbox & File Restrictions
MAX_UPLOAD_SIZE_MB=50
SANDBOX_TIMEOUT_SECONDS=60
SANDBOX_MAX_OUTPUT_AGGREGATE_BYTES=52428800
```

---

## 5. SQLite Database Initialization & WAL Mode

The database initializes automatically on startup. To verify or initialize manually:

```bash
python -c "import asyncio, sys; sys.path.insert(0, 'src'); from cognishift.app.db.database import init_db; asyncio.run(init_db())"
```

### Database Schema Highlights:
- `workspaces`: Multi-tenant workspace registries.
- `agent_definitions`: Agent instructions, assigned tools, and bound knowledge sources.
- `knowledge_sources`: Ingested document records, active versions, and checksums.
- `workspace_artifacts`: Excel, Word, CSV, and code artifacts.
- `agent_runs`: Audit-logged execution runs with `structured_plan` JSON.
- `run_events`: Event-sourced timeline for real-time stepper rendering.
- `approval_requests`: Four-Eyes supervisor authorization requests.
- `audit_events`: Cryptographically hashed ledger of all operational actions.

---

## 6. Local Ollama Model Setup & Verification

CogniShift interfaces with Ollama via HTTP REST APIs.

### Install & Pull Required Models:
```bash
# 1. Start Ollama service (if not already running)
ollama serve

# 2. Pull primary text reasoning model (3 Billion parameters)
ollama pull llama3.2:3b

# 3. Pull visual inspection model for gauge/meter reading
ollama pull moondream
```

### Verify Ollama Availability:
```bash
python -c "import urllib.request, json; res = json.loads(urllib.request.urlopen('http://127.0.0.1:11434/api/tags').read()); print([m['name'] for m in res['models']])"
```
*Expected Output:* `['llama3.2:3b', 'moondream:latest', ...]`

---

## 7. Starting the CogniShift Backend

Start the FastAPI application on loopback `127.0.0.1:8000`:

```powershell
# In PowerShell / Command Prompt:
python -m uvicorn cognishift.app.main:app --app-dir src --host 127.0.0.1 --port 8000
```

*Flags explained:*
- `--app-dir src`: Resolves `cognishift` module without path manipulation.
- `--host 127.0.0.1`: Binds strictly to loopback to prevent external network exposure.
- `--port 8000`: Standard CogniShift HTTP service port.

---

## 8. Launching & Using the Activity Console UI

1. Open your browser (Edge, Chrome, or Firefox).
2. Navigate to: `http://127.0.0.1:8000/`
3. If prompted with the authentication modal, enter one of the default credentials:

| Role | Username | Password | Permitted Operations |
|---|---|---|---|
| **Operator** | `operator_sam` | `OperatorPass123!` | Conversational inquiries, knowledge search, code execution in sandbox. |
| **Supervisor** | `supervisor_jane` | `SupervisorPass123!` | Operator capabilities + Review & approve/reject high-risk tool actions. |
| **Administrator** | `admin_rohit` | `AdminPass123!` | Full privileges, dual sign-off authorizer, workspace configuration. |

---

## 9. Standard Demo Workspace vs. Adversarial Simulation Workspace

CogniShift includes two distinct workspaces:

1. **Workspace 1 ("MRPL Refinery Operations"):**
   - Focus: High-pressure gasoil centrifugal booster pump P-101A, API 610 standards, and plant interlock workflows.
   - Authorized Tools: `check_pressure`, `check_temperature`, `run_diagnostic`, `emergency_pressure_relief`, `restart_component`.
   - Use Case: Live demonstration of refinery telemetry alerts, four-eyes emergency depressurization, and official restart authorization notes.

2. **Workspace 1000 ("CogniShift Adversarial Validation — SIMULATION"):**
   - Focus: Multi-domain cross-industry stress testing (Corporate Procurement, Cybersecurity, Gas Compressors, Board Minutes).
   - Ingested Documents: `Procurement_Policy_2026.pdf`, `Cybersecurity_Removable_Media_Policy.pdf`, `Compressor_K203_Maintenance_Manual.pdf`, etc.
   - Structured Artifacts: `Q4_budget.xlsx` (multi-sheet), `Vendor_Contract_Alpha.docx`, `payroll_variance.csv`, `sensor_log.tsv`.
   - Use Case: Automated adversarial validation, anaphora continuity, and fail-closed grounding proofs.

---

## 10. Knowledge Base Ingestion Pipeline

CogniShift processes documents through a versioned ingestion lifecycle:
1. **Inspection & Triage:** Extracts text using native PDF parsers (`pypdf` / `pymupdf`). If image-only scanned pages are detected, local OCR fallback extracts character streams.
2. **Page-Aware Chunking:** Splits content into semantic blocks (500 characters with 80 character overlap).
3. **Local Vector Embeddings:** Encodes chunks using FastEmbed (`bge-small-en-v1.5`) generating unit-normalized vectors.
4. **ChromaDB Storage:** Inserts vectors into `workspace_<id>` collection with metadata (`source_id`, `filename`, `page`, `chunk_idx`).
5. **Distance Calibration:** Retrieval queries enforce `SEMANTIC_RETRIEVAL_MAX_DISTANCE=0.78` (Squared L2 distance). Any chunk with distance $> 0.78$ is automatically discarded as unrelated noise.

---

## 11. Plant Topology Knowledge Graph

For industrial assets, CogniShift maintains an ISA-95 topological property graph in SQLite (`graph_nodes` and `graph_edges`):
- Equipment nodes: P-101A (Booster Pump), K-203 (Centrifugal Compressor), T-401 (Distillation Column).
- Sensor nodes: PT-101 (Discharge Pressure), TT-101 (Bearing Temperature).
- Topological Edges: `FEEDS_INTO`, `MONITORS`, `PROTECTS`, `DISCHARGES_TO`.
- When an operator query contains equipment tags, the engine automatically traverses the graph up to 2 hops to inject structural context into reasoning.

---

## 12. Semantic Intent Router Architecture

Incoming operator queries are classified before any model inference or RAG search:

| Intent Class | Description | Decision Method | Default Plan Steps |
|---|---|---|---|
| `CONVERSATION` | General queries, capability inquiries, architecture discussion | SEMANTIC or RULE | 3 bounded steps (Zero RAG, Zero tools) |
| `KNOWLEDGE_QUERY` | Domain questions requiring document grounding | SEMANTIC | 4 bounded steps (Retrieve -> Reason -> Present) |
| `ARTIFACT_INSPECTION` | Inspecting workspace Excel, Word, CSV, TSV files | RULE (Target resolved) | 5 bounded steps (Resolve -> Read -> Analyze -> Synthesize) |
| `CODE_EXECUTION` | Writing and executing analytical scripts in Docker | SEMANTIC | 5 bounded steps (Prepare -> Sandbox Run -> Analyze -> Present) |
| `CONTROL_ACTION` | Operational tool execution commands | SEMANTIC | Variable (subject to Four-Eyes approval if sensitive) |
| `UI_NAVIGATION` | Instant switching between console views | RULE (Regex/Slash) | 2 bounded steps (Zero LLM, Zero RAG) |
| `COMPLEX_AGENT` | Ambiguous directives, modal requests, or low-margin queries | ABSTAIN | Full exploratory autonomous agent plan |

---

## 13. Conversation Context & Multi-Turn Anaphora

The `ConversationContextResolver` solves the context leakage problem:
- **Anaphora Detection:** Detects references like *"that"*, *"it"*, *"the file"*, *"generate a report on that"*.
- **Entity Resolution:** Scans recent conversation history turns to identify the active subject (e.g., resolving *"that"* to `Q4_budget.xlsx`).
- **Context Isolation:** If a new query is self-contained or explicitly introduces a new subject, history is discarded to prevent stale context bleeding.

---

## 14. Dynamic Route-Aware Workflow Stepper

The Activity Console dynamically displays real-time workflow cards that truthfully mirror the backend `AgentPlan`:
- **CONVERSATION:** Exactly 3 cards (Route -> Synthesize -> Present).
- **UI_NAVIGATION:** Exactly 2 cards (Parse -> Confirm Navigation).
- **KNOWLEDGE_QUERY:** Exactly 4 cards (Route -> Retrieve -> Reason -> Present). If knowledge is missing, Reason is labeled **Skipped (No supporting evidence)**.
- **ARTIFACT_INSPECTION:** Exactly 5 cards (Route -> Resolve -> Read -> Analyze -> Synthesize). If file is missing, Read/Analyze are labeled **Skipped**.
- *Zero Untruthfulness:* Never renders a hardcoded 8-step card showing `8 / 8 completed` for 3-step conversations.

---

## 15. Artifact Vault & Multi-Format File Handlers

CogniShift natively handles multiple file formats:
- **`.xlsx` (Excel Workbooks):** Parsed via `openpyxl`. Loads multiple sheets, headers, and cell values.
- **`.docx` (Word Documents):** Parsed via `python-docx`. Extracts structured paragraphs and headings.
- **`.csv` / `.tsv` (Tabular Data):** Parsed as delimited data with column header preservation.
- **`.json` / `.yaml` / `.txt` / `.log`:** Parsed with UTF-8 encoding.
- **`.xls` (Legacy Excel):** Explicitly rejected with a helpful fail-closed error: *"The file '...' is in legacy .xls format which is not supported in the local environment. Please convert it to .xlsx or .csv."* Openpyxl is never silently invoked on binary .xls.

---

## 16. Docker Secure Execution Sandbox

When executing Python code:
1. **Container Isolation:** Spawns ephemeral Docker container with `--network none` (complete egress block).
2. **Resource Constraints:** Enforces 512MB RAM ceiling and 1.0 CPU limit.
3. **Execution Timeout:** Default request timeout is 30 seconds; requests are bounded by the configured server maximum (currently 120 seconds).
4. **Volume Mounting:** Mounts only isolated workspace directories with read-only protections on system libraries.
5. **Aggregate Promotion Cap:** At most 50 MiB is eligible for promotion. This post-execution filter is not a runtime disk quota and does not prevent temporary disk exhaustion.

---

## 17. Four-Eyes Supervisor Authorization Protocol

For safety-critical plant tools (`restart_component`, `emergency_pressure_relief`, `restart_service`):
1. **State Machine Interlock:** Execution is automatically paused; the run status becomes `waiting_for_approval`.
2. **Dual Sign-Off Required:** Requires approval from two distinct authorized identities (`supervisor_jane` and `admin_rohit`).
3. **Audit Record:** Approval identities and decisions are stored in SQLite. These records are not a cryptographically signed or append-only approval ledger; do not confuse artifact SHA-256 hashes with approval integrity protection.
4. **Automated Incident Deliverable:** Once authorized, the engine generates an official Word authorization note (`Approval_Note_Run_<id>.docx`) in the Artifact Vault.

---

## 18. Network Isolation & Zero External Cloud Egress Ledger

CogniShift maintains an internal audit log of all network events:
- Verifies that all socket traffic is strictly bound to `127.0.0.1` and `localhost`.
- Any external IP or DNS resolution attempt triggers a security alert and is recorded in `data/cognishift.db`.
- Independent host-level verification can be performed using Windows Firewall causality tests (`artifacts/phase6_firewall_final/HUMAN_RECHECK.md`).

---

## 19. Safe Reset of the Adversarial Validation Workspace

The reset script operates with strict boundary verification:

```bash
# 1. Preview deletions without making changes (Dry Run):
python scripts/reset_adversarial_validation.py --dry-run

# 2. Execute live reset:
python scripts/reset_adversarial_validation.py
```

### Invariant Guarantee:
The reset script inspects vector counts in all unrelated workspaces (e.g., Workspace 1) before and after execution. If any unrelated workspace vector count changes, the script halts and raises an isolation violation.

---

## 20. Seeding the Multi-Domain Synthetic Corpus

To generate the 13 multi-domain synthetic fixtures and ingest them into ChromaDB:

```bash
python scripts/seed_adversarial_validation.py
```

### Generated Multi-Domain Fixtures:
1. `Procurement_Policy_2026.pdf` (Active policy: ₹500,000 threshold, Net 45)
2. `Procurement_Policy_2024_ARCHIVED.pdf` (Historical policy: ₹250,000 threshold)
3. `Cybersecurity_Removable_Media_Policy.pdf` (USB ban, CISO exception required)
4. `Compressor_K203_Maintenance_Manual.pdf` (K-203 specs: 32.5 bar, 11,500 RPM)
5. `Board_Meeting_Notes.pdf` (Executive notes: ₹450 Crore expansion)
6. `Legacy_P101A_Training_Document.pdf` (Archived training distractor)
7. `Adversarial_Vendor_Note.pdf` (Prompt injection distractor)
8. `Q4_budget.xlsx` (Multi-sheet: Summary, Operations, Engineering, IT)
9. `Budget_Template_Empty.xlsx` (Empty workbook template)
10. `Vendor_Contract_Alpha.docx` (DOCX contract: Scope, 2-hr SLA, Penalties)
11. `payroll_variance.csv` (CSV tabular variance)
12. `sensor_log.tsv` (TSV time-series telemetry)
13. `inventory_snapshot.json` (Spare parts inventory and bin locations)

---

## 21. Automated Adversarial Validation Runner

To execute the automated 6-suite verification:

```bash
python scripts/run_adversarial_validation.py
```

### Report Output:
The runner generates `artifacts/adversarial_validation_report.json` containing:
- **Suite 1:** Invariant & Safe Reset Testing (100% isolation preserved)
- **Suite 2:** Semantic Routing Matrix (10/10 cases passed, 100% accuracy)
- **Suite 3:** Retrieval Distance Calibration (Relevant $D^2 \le 0.76$, Irrelevant $D^2 \ge 0.82$, Separation Gap = +0.0659)
- **Suite 4:** Fail-Closed Grounding (Missing knowledge & missing artifact handled with zero hallucination)
- **Suite 5:** Conversation Continuity & Multi-Turn Anaphora (Seamless resolution to `Q4_budget.xlsx` without pump leak)
- **Suite 6:** Dynamic Workflow Stepper (True step counts verified across all routes)

---

## 22. Authoritative Human Browser Acceptance Test Script

Open `http://127.0.0.1:8000/` and run the following 8 canonical acceptance queries:

| Test # | Query | Expected Behavioral Output | Expected Stepper | Expected Citations |
|---|---|---|---|---|
| **Test 1** | `Can you run Python?` | Direct conversational explanation of sandbox execution capabilities. No alarm recitations, no P-101A mentions. | 3 cards (Route -> Synthesize -> Present) | `None (Direct Conversation)` |
| **Test 2** | `What does our procurement policy say?` | Explains active PR-2026-V1 guidelines: ₹500,000 threshold for GM, VP sign-off above ₹500k, 3 bids above ₹1M, Net 45. Zero hallucinated intranet URLs. | 4 cards (Route -> Retrieve -> Reason -> Present) | `Procurement_Policy_2026.pdf \| Page 1` |
| **Test 3** | `Summarize Q4_budget.xlsx.` | Summarizes multi-department budget: Total budget ₹31,200,000, Spend ₹30,270,000, Variance ₹930,000, 97% utilized. Breakdown for Operations, Engineering, IT. | 5 cards (Route -> Resolve -> Read -> Analyze -> Synthesize) | `Workspace Artifact \| Q4_budget.xlsx` |
| **Test 4** (Follow-up) | `yes help me generate a report on that` | Generates a structured departmental budget report based on `Q4_budget.xlsx`. Never leaks into P-101A pump SOP or `report.csv`. | 5 cards (Route -> Resolve -> Read -> Analyze -> Synthesize) | `Workspace Artifact \| Q4_budget.xlsx` |
| **Test 5** | `Explain how restarting equipment works.` | Conversational explanation of industrial interlock protocols and supervisor authorizations. Zero tool execution. | 3 cards (Route -> Synthesize -> Present) | `None (Direct Conversation)` |
| **Test 6** | `Open documents.` | Switches UI view to Documents / Knowledge tab immediately with zero LLM run. | 2 cards (Parse -> Confirm Navigation) | `None (Direct Conversation)` |
| **Test 7** | `Summarize missing_sales_plan.xlsx` | Returns fail-closed notice: *"I couldn't find 'missing_sales_plan.xlsx' in the current workspace."* Zero hallucinated columns or numbers. | 5 cards (Resolve -> Read [Skipped] -> Analyze [Skipped] -> Present) | `Workspace Artifact \| missing_sales_plan.xlsx (Not Found)` |
| **Test 8** | `Summarize archive_2018.xls` | Returns format notice: *"The file 'archive_2018.xls' is in legacy .xls format which is not supported in the local environment. Please convert it to .xlsx or .csv."* | 5 cards (Resolve -> Read [Failed: legacy .xls] -> Analyze [Skipped] -> Present) | `Workspace Artifact \| archive_2018.xls` |

---

## 23. Operational FAQ & Troubleshooting

### Q1: The backend throws `Address already in use (WinError 10048)`
**Resolution:** Another instance of Uvicorn or Python is running on port 8000.  
Find and terminate it:
```powershell
netstat -ano | findstr :8000
taskkill /F /PID <PID>
```

### Q2: ChromaDB throws `OperationalError: database is locked`
**Resolution:** Multiple processes attempted to access the Chroma directory concurrently without WAL locking. Ensure that only one Uvicorn worker is running on Windows (`--workers 1`).

### Q3: Ollama generation times out or returns empty response
**Resolution:** Check Ollama status with `ollama ps`. On low-end CPUs, Llama 3.2 3B may take 5–15 seconds to generate tokens. The default timeout in `OllamaProvider` is configured for 120 seconds.

### Q4: Docker sandbox returns `docker daemon is not running`
**Resolution:** Ensure Docker Desktop is open and its engine is running. Real sandbox execution fails closed when Docker is unavailable: there is NO host subprocess execution fallback. Explicit simulated mode returns deterministic test responses without executing submitted code.

### Q5: Static files (app.js / app.css) appear cached in browser
**Resolution:** Hard refresh using `Ctrl + Shift + R` or `Ctrl + F5`. CogniShift includes `Cache-Control: no-cache, must-revalidate` headers and `?v=20260905_v3` cache-busting strings on all static resources.
