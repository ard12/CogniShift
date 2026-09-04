# CogniShift: Systems Architecture Specification

Technical architecture document for the on-premise agentic AI workbench.

**Validated:** 2026-09-04 against the 219-test non-frontend regression suite and live Docker, RapidOCR, Ollama, and browser workflows. The complete local working tree has 226 passing checks.

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

1. **Web Dashboard:** Browser-based interface at `http://127.0.0.1:8000/static/index.html`.
2. **Terminal CLI:** Typer + Rich command-line application (`cli.py`) for headless edge servers and SSH sessions.
3. **REST API:** OpenAPI / Swagger documentation at `http://127.0.0.1:8000/docs`.
