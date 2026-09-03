# CogniShift — Master System Specification & Implementation Plan

> **SIH26117 Master Blueprint:** Tracks architecture, component interfaces, completed milestones, and delivery phases for the Sovereign On-Premise Agentic AI Workbench.

---

## 1. Project Context & Constraints

* **Host Organization:** Mangalore Refinery and Petrochemicals Limited (MRPL).
* **Mission:** Deliver an air-gapped, zero-cloud agentic AI workbench allowing refinery board operators and field technicians to troubleshoot equipment, query technical SOPs, and safely actuate permitted plant actions.
* **Security Directives:**
  * Zero external cloud egress (100% local Ollama inference on NVIDIA GPU).
  * Zero dynamic shell execution (`subprocess`, `os.system`, `eval`).
  * Non-bypassable Human-in-the-Loop (HITL) Four-Eyes safety gate for sensitive actions.

---

## 2. Phase Delivery Matrix

| Phase | Description | Key Modules | Status |
|:---:|:---|:---|:---:|
| **Phase 1** | Foundation & Air-Gap Verification | `main.py`, `config.py`, `.env` | ✅ **Complete** |
| **Phase 2** | Database Layer & Relational Schemas | `database.py`, `models.py`, `workspaces.py`, `agents.py` | ✅ **Complete** |
| **Phase 3** | Provider Layer & Sovereign Inference | `providers.py`, `ollama_provider.py`, `simulated_provider.py` | ✅ **Complete** |
| **Phase 4** | Knowledge Pipeline & Vector RAG | `retriever.py`, `knowledge.py`, FastEmbed, ChromaDB | ✅ **Complete** |
| **Phase 6** | Industrial Tool Registry & HITL Approvals | `tools.py`, `approvals.py`, `approval_requests` | ✅ **Complete** |
| **Phase 5** | Autonomous Reasoning Engine & Event Ledger | `engine.py`, `runs.py`, `run_events` timeline | ✅ **Complete** |
| **Phase 7** | Multimodal Vision & Gauge OCR | `moondream` integration, Bourdon dial analysis, nameplate OCR | ✅ **Complete** |
| **Phase 8** | Terminal CLI Workbench & Enterprise Polish | `cli.py`, Typer, Rich, interactive REPL | ✅ **Complete** |

---

## 3. Deep-Dive Phase Specifications

### Phase 1: Foundation & Air-Gap Enforcement
* Centralized Pydantic v2 `Settings` class loading from `.env`.
* Startup lifespan handler that ensures local data directory hierarchies exist.
* `/api/v1/system/privacy-status` endpoint verifying that external network egress is blocked.

### Phase 2: Relational Database Layer
* Async SQLite (`aiosqlite`) configured with Write-Ahead Logging (`PRAGMA journal_mode = WAL`) and runtime foreign key enforcement (`PRAGMA foreign_keys = ON`).
* 10 fully normalized tables:
  `workspaces`, `agent_definitions`, `knowledge_sources`, `tool_definitions`, `agent_runs`, `run_events`, `approval_requests`, `audit_events`, `graph_nodes`, `graph_edges`.

### Phase 3: Model Provider Layer
* Abstract base class `ModelProvider` with standard `ModelResponse` dataclass.
* `OllamaProvider` connecting via `httpx.AsyncClient` to `http://localhost:11434` with 120-second timeout resilience.
* `SimulatedProvider` enabling mock CPU testing without active GPU models.

### Phase 4: Knowledge Pipeline (Vector RAG)
* Page-aware PDF parsing using `pypdf`.
* Chunking with 800-character windows and 150-character overlaps preserving `[Filename | Page X]` metadata citations.
* Local CPU embeddings using `fastembed` (`BAAI/bge-small-en-v1.5`) stored in persistent ChromaDB collections.
* Stress-tested successfully on a 500-page mega-manual corpus (787 vector chunks indexed).

### Phase 5: Autonomous Execution Engine
* Reasoning state machine in `src/cognishift/core/engine.py`.
* Ingests Vector RAG context and Plant Topology Graph memory simultaneously.
* Parses model tool-calling intents with JSON extraction and fallback regex parsing.
* Intercepts high-risk actions (`service_interrupting`, `sensitive`) and halts execution in `paused` state.
* Full event sourcing logging each transition (`run_started`, `retrieval_started`, `model_prompt`, `hitl_paused`, `tool_executed`, `completed`) into `run_events`.

### Phase 6: Tools & Safety Approvals
* Deterministic tool simulations in `src/cognishift/core/tools.py` wired to authentic industrial datasets:
  * Dynamic Tennessee Eastman Process SCADA telemetry (`telemetry_stream_tep.json`).
  * SAP S/4HANA PM work orders and ISO 14224 FMEA damage records (`maintenance_orders_sap_pm.json`).
* Supervisor approval inbox in `src/cognishift/app/api/approvals.py` allowing digital sign-off (`approve`/`reject`) to resume paused runs.

### Phase 7: Multimodal Vision & Industrial OCR
* Ingestion of image artifacts (`input_image_path`) in `execute_agent_run`.
* Direct local VLM inference using `moondream:latest` on NVIDIA RTX 3050 GPU.
* Inspection of analog Bourdon pressure dials (extracting tag name `PT-101`, dial reading, and red-zone trip state).
* OCR on stamped metallic equipment rating plates (extracting `P-101A`, Sulzer BB2 model, and API 682 Plan 53A specs).
* Grounded against ISO 15926 Plant Topology Knowledge Graph.

### Phase 8: Terminal CLI Workbench & Enterprise Polish
* Full-featured terminal interface built with Typer + Rich in `src/cognishift/cli.py` (891 lines).
* 8 command groups: `workspace`, `agent`, `knowledge`, `graph`, `telemetry`, `run`, `approvals`, and `chat` (interactive REPL).
* Multimodal support via `--image` flag on `run execute` for local VLM gauge inspection.
* Four-Eyes supervisor sign-off via `approvals approve` / `approvals reject` with audit trail.
* UTF-8 safe on Windows consoles with automatic `stdout` reconfiguration.
* Documented in [`CLI.md`](CLI.md) with complete command reference and terminal output examples.

---

## 4. Benchmark Validation Summary
* **Industrial Workflow Suite:** 5/5 tests passing (`scratch/test_industrial_data_workflow.py`).
* **Multimodal Vision & OCR Suite:** 3/3 scenarios passing (`scratch/test_multimodal_vision_pipeline.py`).
* **Unit & Schema Suite:** 17/17 tests passing (`pytest -v`).
* **Production Metrics Suite:** TCA 100%, SIR 100%, SLCP 100%, FAR 0% (`scratch/evaluate_production_metrics.py`).
