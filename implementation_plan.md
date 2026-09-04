# CogniShift: Master System Specification & Implementation Plan

Master architectural plan tracking system interfaces, completed milestones, and delivery phases for the CogniShift on-premise workbench (SIH26117).

---

## 1. Project Context & Constraints

* **Problem Statement:** SIH26117 (Mangalore Refinery and Petrochemicals Limited).
* **Objective:** Build an on-premise agentic AI workbench allowing plant operators and technicians to query technical manuals, inspect equipment visuals, and safely run permitted plant actions.
* **Key Constraints:**
  * Local model execution using open-weight models via Ollama.
  * No direct host command execution (`subprocess`, `os.system`, `eval`).
  * Policy-enforced human-in-the-loop approval gate for sensitive actions.
  * Containerized execution for AI-generated code.

---

## 2. Phase Delivery Matrix

| Phase | Description | Key Modules | Status |
|:---:|:---|:---|:---:|
| **Phase 0** | Base Security & Test Harness | Test suites, baseline validation | Complete |
| **Phase 1** | Foundation, Config & Local Lifespan | `main.py`, `config.py`, `.env` | Complete |
| **Phase 2** | Database Layer & Relational Schemas | `database.py`, `models.py`, `workspaces.py`, `agents.py` | Complete |
| **Phase 3** | Local Model Provider & Simulated Fallback | `providers.py`, `ollama_provider.py`, `simulated_provider.py` | Complete |
| **Phase 4** | Knowledge Pipeline & Docker Code Sandbox | `retriever.py`, ChromaDB, FastEmbed, Docker sandbox runner | Complete (Verified in live Docker container) |
| **Phase 5** | Multimodal Document Processing | `document_processing/`, Native PDF, RapidOCR, Moondream Vision | Complete & Verified (164 tests passing) |
| **Phase 6** | Network Sovereignty Enforcement & Egress Observation | Network monitoring, egress policy enforcement | Planned (Locked) |
| **Phase 7** | Flagship Industrial Demonstration Workflows | End-to-end industrial scenario demonstrations | Planned (Locked) |

---

## 3. Phase Specifications & Technical Details

### Phase 0: Base Security & Test Harness
* Established automated testing framework with `pytest` and `pytest-asyncio`.
* Configured SQLite in-memory and temporary database fixtures for isolated test runs.

### Phase 1: Foundation & Configuration
* Centralized Pydantic v2 `Settings` class loading configuration from `.env`.
* FastAPI lifespan handler managing startup and shutdown of local resources.
* Local status endpoints reporting system configuration and database health.

### Phase 2: Relational Database Layer
* Async SQLite (`aiosqlite`) with Write-Ahead Logging (`PRAGMA journal_mode = WAL`) and runtime foreign keys (`PRAGMA foreign_keys = ON`).
* 10 normalized tables:
  `workspaces`, `agent_definitions`, `knowledge_sources`, `tool_definitions`, `agent_runs`, `run_events`, `approval_requests`, `audit_events`, `graph_nodes`, `graph_edges`.
* CRUD routers for workspace management and agent definitions with Pydantic validation schemas.

### Phase 3: Model Provider Layer
* Abstract base class `ModelProvider` with dataclass `ModelResponse`.
* `OllamaProvider` connecting via `httpx.AsyncClient` to `http://localhost:11434` with 120-second timeout handling.
* `SimulatedProvider` enabling mock testing without an active GPU.

### Phase 4: Knowledge Pipeline & Docker Code Sandbox
* Vector retrieval using `fastembed` (`BAAI/bge-small-en-v1.5`) running on CPU with persistent ChromaDB vector storage.
* Page-level citation tracking (`[Filename | Page X]`).
* Docker code execution sandbox for generated Python code:
  * Network isolation (`--network none`).
  * Resource limits (512MB RAM, 64 PIDs).
  * Read-only root filesystem with temporary scratch volume.
  * Non-root user execution.

### Phase 5: Multimodal Document Processing
* `DocumentProcessingService` routing documents between:
  * **Native PDF Extraction:** Uses `pypdf` to extract digital text directly.
  * **Local OCR:** Uses `RapidOCR` on CPU for scanned documents and images. Handwriting is best-effort.
  * **Local Vision:** Uses `moondream:latest` via Ollama for interpreting visual elements.
* Provenance tracking: preserves page numbers and processing methods per chunk.
* Untrusted prompt wrapper: wraps extracted text in `<document_context ...>` delimiters with character escaping.

### Phase 6: Network Sovereignty Enforcement (Planned)
* Network egress monitoring and verification.
* Host firewall rules and observation logging to detect unexpected outbound traffic.

### Phase 7: Flagship Industrial Demonstrations (Planned)
* End-to-end operational workflows demonstrating multi-turn operator interactions.
* Comprehensive industrial scenario rehearsals with synthetic SCADA streams and maintenance logs.

---

## 4. Verification & Testing

* **Full Regression Suite:** 164 tests passing with 0 failures (`pytest -v`).
* **Real Container Sandbox:** 16 tests passing in live Docker engine (`tests/test_phase4_real_sandbox.py`).
* **Real OCR & Vision Tests:** Verified against local RapidOCR and Ollama Moondream (`tests/test_phase5_real_ocr.py`, `tests/test_phase5_real_vision.py`).
