# CogniShift: Systems Architecture Specification

Technical architecture document for the on-premise agentic AI workbench.

**Validated:** 2026-09-07 against the complete 401+ test suite (100% passing) and live Docker, RapidOCR, Ollama, and browser workflows.

Authentication uses hashed long-lived bearer credentials plus optional loopback-only, process-memory demo sessions. Demo sessions require `COGNISHIFT_DEMO_MODE=true`, expire automatically, and never expose long-lived keys.

---

## 1. Network & Deployment Model (Industrial DMZ Concept)

CogniShift is designed for local on-premise deployment within an industrial network architecture (such as an Industrial Demilitarized Zone / Purdue Model Level 3.5), operating without external cloud connections:

```
+-----------------------------------------------------------------------+
|  ENTERPRISE / BUSINESS NETWORK                                        |
|  (Workstations, Office Network, Reporting)                            |
+-----------------------------------------------------------------------+
                                   ▲
                          Firewall / DMZ Boundary
                                   ▼
+-----------------------------------------------------------------------+
|  COGNISHIFT ON-PREMISE WORKBENCH (Local Server)                       |
|  • Local Model Inference (Ollama: Llama 3.2 3B + Moondream 1.86B)     |
|  • Local Vector Store (FastEmbed + ChromaDB)                          |
|  • Plant Topology Graph Memory (SQLite WAL)                           |
|  • Human-in-the-Loop Safety Interlocks                                |
|  • Restricted Docker Code Execution Sandbox (--network none)          |
+-----------------------------------------------------------------------+
                                   ▲
                          Firewall / Plant Boundary
                                   ▼
+-----------------------------------------------------------------------+
|  SIMULATED INDUSTRIAL DATA SOURCES                                    |
|  • Dynamic SCADA Telemetry Stream (Tennessee Eastman Process Model)   |
|  • Plant Maintenance Work Orders (SAP PM / ISO 14224 Schema)          |
+-----------------------------------------------------------------------+
```

---

## 2. Knowledge Substrate: Hybrid Search & Topology Graph

CogniShift combines unstructured document search with structured equipment topology:

### 2.1. Vector Retrieval Layer (Unstructured Documents)
* Ingests technical manuals and operating procedures.
* Uses FastEmbed (`BAAI/bge-small-en-v1.5`) to generate 384-dimensional dense vectors on CPU.
* Stores vector embeddings in local ChromaDB collections segregated by `workspace_id`.
* Returns matching text snippets alongside source citations (`[Filename | Page X]`).

### 2.2. Graph Layer (Physical Equipment Topology)
* Stored in local SQLite relational tables:
  * `graph_nodes (id, workspace_id, name, entity_type, properties)`
  * `graph_edges (id, workspace_id, source_node_id, relation_type, target_node_id, properties)`
* Models physical connections between equipment:
  * `Pump-101A` $\xrightarrow{\text{FEEDS\_INTO}}$ `Reactor-B`
  * `Reactor-B` $\xrightarrow{\text{PROTECTED\_BY}}$ `SV-402`
  * `SV-402` $\xrightarrow{\text{DISCHARGES\_TO}}$ `Flare-Header`
  * `Pump-101A` $\xrightarrow{\text{HAS\_SENSOR}}$ `PT-101` (Discharge Pressure)
  * `Pump-101A` $\xrightarrow{\text{HAS\_SENSOR}}$ `TT-204` (Bearing Temperature)
* Multi-hop SQL queries traverse equipment relationships to supply structural context to the language model.

---

## 3. Human-in-the-Loop Safety Interlocks

High-consequence plant operations require explicit human review. Tool definitions specify a risk level (`read_only`, `low_risk`, `sensitive`, `service_interrupting`):

### State Machine Lifecycle:
```
[RUN_STARTED]
      │
[RETRIEVAL] ──► (Vector Search + Equipment Topology + Visual Input)
      │
[MODEL_REASONING]
      │
      ▼
Does Proposed Action Require Approval?
 ├── NO  ──► [EXECUTE_TOOL] ──► [COMPLETE]
 └── YES ──► [TRANSITION TO PAUSED]
                  │
                  ▼
         Queue in approval_requests table
                  │
         Supervisor Review (Web Console / Terminal CLI / REST API)
         ├── REJECT ──► [CANCELLED]
         └── APPROVE ─► [RESUME_RUN] ──► [EXECUTE_TOOL] ──► [COMPLETE]
```

---

## 4. Document Processing, OCR & Vision Pipeline

The pipeline handles three distinct types of document and image inputs:

1. **Native PDF Extraction:** Reads digital text streams embedded directly in vector PDFs using `pypdf`. Fast and accurate for digitally created manuals.
2. **Local OCR (RapidOCR):** Extracts text from scanned document pages and images where no digital text stream exists. Handwriting is processed on a best-effort basis, with OCR confidence scores retained.
3. **Local Vision Model (Moondream):** Interprets visual features in images (e.g., analog pressure gauge needle positions or equipment rating plates) using the local `moondream:latest` model via Ollama.

Extracted text is wrapped in prompt delimiters (`<document_context ...>`) with escaped special characters so the model recognizes it as untrusted input data.

---

## 5. Safe Code Execution (Docker Sandbox)

When agents generate Python code, it is not executed directly on the host operating system:
* Code runs inside a restricted Docker container.
* Network access is disabled (`--network none`).
* Memory and process limits are enforced (`--memory 512m`, `--pids-limit 64`).
* The root filesystem is read-only (`--read-only`) with a temporary, bounded scratch volume for output.
* The container runs as a non-root user.

---

## 6. Network Policy & Sovereignty Enforcement (Phase 6)

CogniShift implements dual-layer network defense to guarantee operational confidentiality:

```
+-------------------------------------------------------------------------------+
| APPLICATION LAYER DEFENSE                                                     |
|                                                                               |
|   OllamaProvider / HTTP Clients                                               |
|         │                                                                     |
|         ▼                                                                     |
|   get_sovereign_async_client() / get_sovereign_client()                       |
|         │                                                                     |
|         ▼                                                                     |
|   SovereignAsyncTransport / SovereignTransport                                |
|         │                                                                     |
|         ├── Hostname Resolution & Classification (ipaddress module)           |
|         ├── Policy Check (NetworkPolicy: STRICT mode)                         |
|         │     ├── Loopback (127.0.0.1, ::1 on ports 11434, 8000) ──► ALLOW   |
|         │     ├── Unapproved Loopback Ports / Private RFC 1918  ──► BLOCK   |
|         │     └── Public Internet / Link-Local Metadata (169.254)──► BLOCK   |
|         └── Audit Logging (network_events table: metadata only)               |
+-------------------------------------------------------------------------------+
                                  │
                                  ▼
+-------------------------------------------------------------------------------+
| OS LAYER DEFENSE (Windows Defender Firewall)                                  |
|                                                                               |
|   Rule Group: CogniShift-Phase6                                               |
|   • Allow Outbound Loopback (127.0.0.1, ::1) for target python.exe            |
|   • Allow Inbound Loopback (port 8000) for FastAPI server                      |
|   • Block Outbound Non-Loopback (WAN/LAN egress) for python.exe               |
+-------------------------------------------------------------------------------+
                                  │
                                  ▼
+-------------------------------------------------------------------------------+
| INDEPENDENT HOST OBSERVER (scripts/observe_network.py)                        |
|                                                                               |
|   • Monitors OS socket table via psutil at regular polling intervals          |
|   • Classifies active connections into loopback, private, and public          |
|   • Validated via negative control (test loopback socket detection)           |
|   • Confirms zero unauthorized external sockets during local workflows        |
+-------------------------------------------------------------------------------+
```

### 6.1. Content Security Policy (CSP) & Header Hardening
All web server responses include:
* `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none';`
* `X-Content-Type-Options: nosniff`
* `X-Frame-Options: DENY`
* `Referrer-Policy: no-referrer`

---

## 7. Operator Interfaces

1. **Production Web Console (SPA):** Modern Single Page Application built with React 19, TypeScript, and Tailwind CSS (located in `frontend/`). Features real-time run timelines, Four-Eyes approval cards, workspace switching, knowledge base ingestion, and inline deliverable preview/download. Served via Vite development server (`http://localhost:5173`) or production-compiled bundle via FastAPI at root (`http://127.0.0.1:8000/`).
2. **Terminal CLI:** Typer + Rich command-line application (`cli.py`) for headless edge servers, air-gapped industrial consoles, and SSH sessions.
3. **REST API:** OpenAPI / Swagger documentation at `http://127.0.0.1:8000/docs`.

---

## 8. Native FastEmbed Semantic Intent Router

CogniShift integrates a zero-cloud, multi-domain intent classification router before model routing:
* **7 Discrete Semantic Intents:**
  1. `CONVERSATION`: Clarifications, greetings, capabilities, questions about what tools exist.
  2. `KNOWLEDGE_QUERY`: Technical manual search, SOP lookups, standard operating tolerances.
  3. `ARTIFACT_INSPECTION`: Inspection or review of generated reports, charts, and spreadsheets.
  4. `CODE_EXECUTION`: Running python data science scripts or sandbox calculations.
  5. `CONTROL_ACTION`: Actuating valves, reading live SCADA telemetry, tripping components.
  6. `UI_NAVIGATION`: Direct interface navigation commands.
  7. `COMPLEX_AGENT`: Multi-step diagnostic synthesis requiring iterative reasoning.
* **Entity Decoupling & Normalization:** Identifies file extensions, equipment tags (`PT-101`, `P-101A`), and replaces them with normalized tokens (`<equipment_id>`, `<file>`) to ensure routing is invariant to specific equipment IDs.
* **Cosine Distance & Confidence Margins:** Computes embeddings via local `BAAI/bge-small-en-v1.5` on CPU; requires minimum confidence and runner-up margin thresholds; safely abstains (`DecisionMethod.ABSTAIN`) when queries are ambiguous.

---

## 9. Multi-Turn Conversational Engine & CAS Pending Tasks

CogniShift manages multi-turn conversational continuity and delayed human authorizations via an atomic state machine:
* **Atomic Compare-And-Swap (CAS):** State transitions (`PENDING` → `CLAIMED` → `EXECUTING` → `COMPLETED`/`FAILED`) use atomic SQL updates (`UPDATE pending_tasks SET status = 'CLAIMED' WHERE id = ? AND status = 'PENDING'`) preventing race conditions or double execution.
* **Affirmation Resumption:** When a high-risk proposal is paused, subsequent affirmations (e.g. *"yes do it"*, *"proceed"*, *"confirmed"*) automatically associate with the active task.
* **Safe Cancellation:** Operators can abort pending operations (e.g. *"cancel that"*, *"stop"*, *"abort"*) without triggering side effects.
* **15-Minute TTL Eviction:** Unclaimed or expired pending tasks fail closed and are marked `EXPIRED` to prevent stale actions from lingering.

---

## 10. Multi-Format Deliverable Generation Pipeline

CogniShift features an industrial artifact generation pipeline that produces professional engineering deliverables:
* **Supported Formats:**
  - **Spreadsheets (`.xlsx`):** Multi-tab workbooks via `openpyxl` with financial audits, operational telemetry, and styled KPI summaries.
  - **Documents (`.docx`):** Formal engineering memos and audit reports via `python-docx`.
  - **Vector Reports (`.pdf`):** Publication-quality documents via `reportlab` with exact margins and tables.
  - **Visualizations (`.png`):** High-resolution trend plots and multi-panel charts via `matplotlib` and `seaborn`.
  - **Structured Datasets (`.json`):** Machine-readable telemetry and audit logs.
* **Cryptographic Change Detection:** Computes SHA-256 digests for all generated artifacts; rejects tampered files at download time (HTTP 409 Conflict).
* **Workspace Containment:** Artifacts are strictly quarantined within per-workspace subdirectories (`data/workspaces/{id}/generated/`).

