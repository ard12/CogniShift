# Developer Alignment Guide (AI to AI Handoff & Synchronization)

This document outlines technical alignment between developer assistants working on CogniShift. Read this guide to understand system contracts, active boundaries, and development status.

---

## 1. Operating Constraints

CogniShift is an on-premise agentic AI workbench developed for problem statement SIH26117:
* **Local Operation:** The system is designed to run locally without external cloud APIs (no OpenAI, Gemini, or Anthropic API dependencies at runtime).
* **No Arbitrary Host Execution:** No direct execution of arbitrary shell commands via `subprocess.run`, `os.system`, `exec()`, or `eval()` on the host system. AI-generated code execution runs inside isolated Docker containers.
* **Hardware Allocation:**
  * **GPU Host:** Runs local LLM (`llama3.2:3b`) and vision (`moondream:latest`) inference via Ollama, agent reasoning loops, multimodal processing, and local integration tests.
  * **CPU Host:** Runs FastAPI endpoints, SQLite relational queries, FastEmbed document ingestion, and the operator interface.

---

## 2. Project Status & Phases

The repository follows a sequential phase architecture:

| Phase | Description | Status |
|:---|:---|:---:|
| **Phase 0** | Base Security & Test Harness | Complete |
| **Phase 1** | Foundation, Config & Local Lifespan | Complete |
| **Phase 2** | Database Layer (aiosqlite WAL, 10 tables) & CRUD Routers | Complete |
| **Phase 3** | Local Model Provider (`OllamaProvider`) & Simulated Fallback | Complete |
| **Phase 4** | Knowledge Pipeline (ChromaDB + FastEmbed) & Docker Code Sandbox | Complete (Verified in live Docker container) |
| **Phase 5** | Multimodal Document Processing (Native PDF, RapidOCR, Moondream Vision) | Complete & Verified |
| **Phase 6** | Network Sovereignty Enforcement & Egress Observation | Planned (Locked) |
| **Phase 7** | Flagship Industrial Demonstration Workflows | Planned (Locked) |

Do NOT begin Phase 6 or Phase 7 implementation until explicitly authorized.

---

## 3. Core Contracts & Interfaces

### A. Vector Retrieval Contract (`src/cognishift/core/retriever.py`)
```python
async def retrieve_context(workspace_id: int, query: str, top_k: int = 3) -> str:
    """Searches ChromaDB for the given query within the workspace.
    Returns a formatted string containing chunk text and [Filename | Page X] citations.
    """
```

### B. Plant Topology Graph Query Contract (`src/cognishift/core/graph_memory.py`)
```python
async def query_graph_context(workspace_id: int, query_text: str, max_hops: int = 2) -> str:
    """Traverses SQLite graph_nodes and graph_edges matching equipment mentioned in query_text.
    Returns structured relationship text (e.g., Pump-101A --(FEEDS_INTO)--> Reactor-B).
    """
```

### C. Tool Registry Contract (`src/cognishift/core/tools.py`)
```python
async def execute_tool(tool_name: str, parameters: dict) -> str:
    """Executes registered tool functions against simulated plant telemetry
    and synthetic maintenance records without running shell commands.
    """
```

### D. Agent Execution Loop Contract (`src/cognishift/core/engine.py`)
```python
async def execute_agent_run(
    workspace_id: int,
    agent_id: int,
    input_text: str,
    user_id: str = "operator",
    input_image_path: Optional[str] = None
) -> RunResponse:
    """Executes the agent reasoning loop. If an image path is provided, it is analyzed
    by the local vision model before context retrieval. If a tool requires approval,
    the run transitions to 'paused' and records an approval request.
    """

async def resume_agent_run(run_id: int) -> RunResponse:
    """Resumes execution of a paused run once a supervisor has recorded an approval."""
```

### E. Document Processing Contract (`src/cognishift/core/document_processing/service.py`)
```python
class DocumentProcessingService:
    async def process_document(
        self,
        workspace_id: int,
        source_id: int,
        file_path: Path,
        preferred_method: str = "auto"
    ) -> DocumentProcessingResult:
        """Processes a PDF using native PDF text extraction, OCR, or vision interpretation
        depending on document structure, while tracking page-level provenance.
        """
```

---

## 4. Operator Interfaces

CogniShift provides three operator interfaces:

| Interface | Access Point | Description |
|:---|:---|:---|
| **Web Console** | `http://127.0.0.1:8000/static/index.html` | Browser-based dashboard for uploads, agent runs, and approvals |
| **REST API** | `http://127.0.0.1:8000/docs` (Swagger UI) | Interactive OpenAPI documentation and test client |
| **Terminal CLI** | `python cli.py [command]` | Terminal interface built with Typer and Rich for headless setups |

---

## 5. Development Guidelines

1. Run the test suite with `pytest -v` before committing. All tests must pass with 0 failures.
2. Keep all external network requests disabled during testing.
3. Validate workspace and source ownership server-side for every operation.
4. Treat all extracted document text as untrusted data using the prompt delimiter wrapper.
