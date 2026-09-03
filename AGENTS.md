# Agentic Alignment Guide (AI to AI Handoff & Synchronization)

> **HELLO FELLOW AI ASSISTANT!** 👋  
> This document governs technical alignment between developer agents assisting **Sitanshu** and **Rohit**. Read this guide carefully to preserve all architectural contracts and avoid breaking changes.

---

## 1. Operating Constraints (Non-Negotiable)

We are building a **Sovereign On-Premise Agentic AI Workbench** (SIH26117).
* **Zero Cloud:** The system must operate 100% offline. Never introduce external endpoints (OpenAI, Gemini, Anthropic, HuggingFace Hub downloads at runtime).
* **Zero Arbitrary Execution:** Never use `subprocess.run`, `os.system`, `exec()`, or `eval()`.
* **Hardware Specialization:**
  * **Sitanshu (NVIDIA RTX 3050 GPU):** Runs local LLM (`llama3.2:3b`) and VLM (`moondream:latest`) inference, Autonomous Execution Engine (`engine.py`), Multimodal Vision, and Industrial Benchmark suites.
  * **Rohit (CPU Host):** Focuses on Platform APIs, FastEmbed document ingestion, SQLite relational queries, and Operator Console UI.

---

## 2. Completed Milestones & Current Standing

All foundational and core reasoning phases are **100% complete and passing on `main`**:
1. **Phase 1 (Foundation):** Lifespan handler, configuration singleton, air-gap status endpoints.
2. **Phase 2 (Database):** Async SQLite (`aiosqlite`) with 10 tables including `graph_nodes`, `graph_edges`, and `run_events`.
3. **Phase 3 (Providers):** Local `OllamaProvider` with 120s timeout resilience and `SimulatedProvider` dev fallback.
4. **Phase 4 (Knowledge Pipeline):** Page-aware PyPDF extraction, CPU-friendly FastEmbed, and ChromaDB vector store (`retriever.py`).
5. **Phase 6 (Tools & Approvals):** Data-driven tool execution (`tools.py`) and supervisor approval management (`approvals.py`).
6. **Phase 5 (Execution Engine):** State machine agent reasoning loop (`engine.py`) with automatic Four-Eyes HITL pausing.
7. **Phase 7 (Multimodal Vision):** Moondream integration for analog pressure gauge dial readings and stamped metallic nameplate OCR.

---

## 3. Public Contracts & Interfaces (Do Not Break!)

### A. Vector RAG Contract (`src/cognishift/core/retriever.py`)
```python
async def retrieve_context(workspace_id: int, query: str, top_k: int = 3) -> str:
    """Searches ChromaDB for the given query within the workspace.
    Returns a formatted string containing chunk text and [Filename | Page X] citations.
    """
```

### B. Plant Topology Graph Memory Contract (`src/cognishift/core/graph_memory.py`)
```python
async def query_graph_context(workspace_id: int, query_text: str, max_hops: int = 2) -> str:
    """Traverses SQLite graph_nodes and graph_edges matching physical equipment in query_text.
    Returns structured relationship strings (e.g. Pump-101A --(FEEDS_INTO)--> Reactor-B).
    """
```

### C. Industrial Tool Registry Contract (`src/cognishift/core/tools.py`)
```python
async def execute_tool(tool_name: str, parameters: dict) -> str:
    """Executes data-driven tool logic against Tennessee Eastman Process telemetry
    and SAP S/4HANA PM work orders without arbitrary shell commands.
    """
```

### D. Autonomous Engine Execution Contract (`src/cognishift/core/engine.py`)
```python
async def execute_agent_run(
    workspace_id: int,
    agent_id: int,
    input_text: str,
    user_id: str = "operator",
    input_image_path: Optional[str] = None
) -> RunResponse:
    """Executes end-to-end reasoning loop. If input_image_path is provided, analyzes
    with local Moondream VLM before RAG retrieval. If high-risk action is detected,
    safely pauses run in approval_requests.
    """

async def resume_agent_run(run_id: int) -> RunResponse:
    """Resumes execution of a paused run once the supervisor signs off in approval_requests."""
```

---

## 4. Current Work: Phase 8 (Integration & Qualifier Rehearsal)
With all core AI, database, RAG, tool, graph, and vision modules complete and verified, our next joint step is preparing the final demonstration flows and ensuring flawless presentation timing for SIH qualifiers.
