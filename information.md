# CogniShift: Project Guide & Technical Overview

This guide explains what CogniShift is, why it was built, and how its components work together in plain, technical English.

---

## 1. What is CogniShift?

### The Problem
Industrial facilities like refineries and chemical plants handle complex, safety-critical equipment operating at high temperatures and pressures. When technicians and board operators troubleshoot issues:
1. **Large Documentation Sets:** Equipment manuals, P&IDs (Piping and Instrumentation Diagrams), and operating procedures span hundreds or thousands of pages.
2. **Confidentiality Requirements:** Plant schematics, maintenance histories, and operating data cannot be sent to public cloud AI services due to infrastructure security policies.
3. **Safety Requirements:** An AI assistant must never have unverified authority to operate equipment or change operating setpoints. High-risk actions require explicit human approval.

### The CogniShift Approach
CogniShift is an on-premise agentic AI workbench:
* **Local Model Execution:** Runs open-weight models (`llama3.2:3b` for reasoning and `moondream` for vision) locally via Ollama.
* **Combined Document & Topology Search:** Searches PDF manuals with page-level citations and queries a local plant equipment graph to understand physical relationships.
* **Visual Inspection:** Uses a local vision model to read analog pressure gauge dials and equipment nameplates from photos.
* **Human Review for Sensitive Actions:** When a proposed tool action is classified as sensitive or service-interrupting, the system pauses execution and waits for a supervisor's approval.
* **Isolated Code Execution:** AI-generated Python code runs inside a restricted Docker container with no network access.

---

## 2. Architecture & Data Flow

```
+-------------------------------------------------------------------------------+
|  1. OPERATOR INTERFACES                                                       |
|     Web Console (/static/index.html), Terminal CLI (cli.py), REST API (/docs) |
+---------------------------------------+---------------------------------------+
                                        |
        +-------------------------------+-------------------------------+
        |                                                               |
+-------v-------------------------------+       +-----------------------v-------+
|  2. RELATIONAL DATABASE (aiosqlite)   |       |  3. VECTOR KNOWLEDGE BASE     |
|     Stores workspaces, agent specs,   |       |     (ChromaDB + FastEmbed)    |
|     runs, approvals, and event logs.  |       |     Indexes PDF manuals with  |
+---------------------------------------+       |     page-number citations.    |
        |                                       +-------------------------------+
        +-------------------------------+-------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|  4. PLANT TOPOLOGY GRAPH (SQLite: graph_nodes & graph_edges)                 |
|     Tracks physical equipment connections (e.g., Pump-101A -> Reactor-B).     |
+---------------------------------------+---------------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|  5. LOCAL MODEL INFERENCE (Ollama: Llama 3.2 3B + Moondream 1.86B)           |
|     Performs text reasoning and visual inspection on local hardware.          |
+---------------------------------------+---------------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|  6. TOOL EXECUTION & APPROVAL GATE                                            |
|     Read-only tools run immediately. Sensitive actions pause the run until   |
|     approved by a supervisor. Generated code runs in a Docker sandbox.       |
+-------------------------------------------------------------------------------+
```

---

## 3. Component Reference

### Web Server & Configuration
* **`src/cognishift/app/main.py`:** Main FastAPI application setup, router mounting, and lifespan management.
* **`src/cognishift/app/config.py`:** Settings configuration using Pydantic v2.
* **`src/cognishift/app/static/index.html`:** Web operator console for document uploads, runs, and approvals.

### Database & Relational Storage
* **`src/cognishift/app/db/database.py`:** Async SQLite connection management using `aiosqlite` with WAL mode enabled.
* **`src/cognishift/app/db/models.py`:** Pydantic schemas for request and response validation.

### Knowledge & Context Retrieval
* **`src/cognishift/core/retriever.py`:** Chunks and embeds documents into ChromaDB using FastEmbed on CPU, returning text with page citations.
* **`src/cognishift/core/graph_memory.py`:** Queries equipment connection relationships from SQLite graph tables.

### Document Processing (Phase 5)
* **`src/cognishift/core/document_processing/service.py`:** Routes document processing between native PDF extraction, RapidOCR, and Moondream vision.
* **`src/cognishift/core/document_processing/native_pdf.py`:** Extracts text from digitally created PDFs using `pypdf`.
* **`src/cognishift/core/document_processing/ocr_provider.py`:** Local CPU-based OCR using `RapidOCR` for scanned pages. Handwriting is best-effort.
* **`src/cognishift/core/document_processing/vision_service.py`:** Local GPU-based visual analysis using `moondream`.
* **`src/cognishift/core/document_processing/provenance.py`:** Page provenance tracking and untrusted data wrapping with delimiter escaping.

### Model Providers & Engine
* **`src/cognishift/core/providers.py`:** Model provider abstract interface and factory.
* **`src/cognishift/core/ollama_provider.py`:** Client for local Ollama service.
* **`src/cognishift/core/simulated_provider.py`:** Mock provider for testing without local models.
* **`src/cognishift/core/engine.py`:** Agent execution loop, tool detection, and approval pause state machine.
* **`src/cognishift/core/tools.py`:** Registered tool definitions and execution functions.

### Network Sovereignty & Policy (Phase 6)
* **`src/cognishift/core/network/schemas.py`:** Network destination models, policy modes (`STRICT`, `DEVELOPMENT`), and exceptions.
* **`src/cognishift/core/network/resolver.py`:** Standard library IP classification (`ipaddress`), DNS resolution, and multi-IP rebinding protection.
* **`src/cognishift/core/network/policy.py`:** Deterministic policy engine enforcing loopback allowlists and private/public isolation.
* **`src/cognishift/core/network/guard.py`:** Custom `SovereignAsyncTransport` and `SovereignTransport` intercepting HTTP connections.
* **`src/cognishift/core/network/client.py`:** Centralized factory `get_sovereign_async_client()` and `get_sovereign_client()`.
* **`src/cognishift/core/network/events.py`:** SQLite audit ledger management with metadata logging and retention limits.
* **`src/cognishift/core/network/preflight.py`:** Startup validation for local models, offline cache, OCR, Docker sandbox, and frontend CDN footprint.
* **`scripts/observe_network.py`:** Independent host socket observer with negative control validation.
* **`scripts/enable_strict_network_policy.ps1`:** Operator PowerShell script for Windows Defender Firewall enforcement.

### Terminal CLI
* **`cli.py` & `src/cognishift/cli.py`:** Terminal interface built with Typer and Rich for managing workspaces, agents, knowledge, telemetry, runs, and approvals.

---

## 4. Simulated Operational Scenarios

### Scenario 1: Sensor Reading Check
* **Operator Request:** *"Check the pressure on sensor PT-101."*
* **Workflow:** Agent selects tool `check_pressure(sensor_id="PT-101")` $\rightarrow$ System checks risk level (`read_only`) $\rightarrow$ Executes immediately $\rightarrow$ Returns simulated reading (e.g., `105.5 PSI [NOMINAL]`).

### Scenario 2: High-Pressure Condition with Supervisor Review
* **Condition:** Simulated telemetry reports pressure exceeding threshold.
* **Workflow:** Agent retrieves safety limits from operating manual $\rightarrow$ Recommends relief valve actuation $\rightarrow$ System identifies tool as `service_interrupting` $\rightarrow$ Run transitions to `paused` $\rightarrow$ Supervisor inspects request and clicks approve $\rightarrow$ Engine resumes and executes action.

### Scenario 3: Analog Gauge Visual Inspection
* **Operator Input:** Uploads a photo of an analog pressure gauge.
* **Workflow:** Local Moondream vision model inspects the image $\rightarrow$ Estimates needle position and dial units $\rightarrow$ Reasoning model compares reading against manual limits.

---

## 5. Frequently Asked Questions

**Why run models locally?**
Refinery operating procedures, schematics, and sensor data are confidential. Running models on-premise ensures that data remains within the local network.

**How are hallucinations reduced?**
The system uses retrieval-augmented generation (RAG) to ground answers in indexed manuals with explicit page-number citations, and cross-checks equipment connections against the topology graph.

**Can an agent actuate equipment on its own?**
No. Tools are tagged with risk levels. Any action classified as sensitive or service-interrupting is intercepted by infrastructure code and held in a paused state until approved by a human supervisor.

**What happens if a document contains conflicting instructions?**
Retrieved text is presented with its source filename and page number, allowing operators to verify the authoritative manual. Extracted text is wrapped in untrusted data delimiters to reduce the risk of prompt injection.
