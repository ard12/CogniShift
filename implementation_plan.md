# CogniShift — Master System Specification & Sync Plan

> **ATTENTION AI ASSISTANTS:** This document is the ultimate source of truth for the CogniShift project. Two human developers (Sitanshu and Rohit) are using separate AI assistants to build this system. You must strictly adhere to the boundaries, interfaces, and constraints defined here to ensure the code you generate integrates flawlessly with the other team's code.

---

## 1. Project Context & Non-Negotiable Constraints

**Target:** SIH26117 — Sovereign On-Premise Agentic AI Workbench for Mangalore Refinery and Petrochemicals Limited (MRPL).
**Core Purpose:** An industrial helpdesk/agentic platform where users can query manuals and safely execute simulated industrial actions.

### 🚫 Strict Security & Hardware Constraints
1. **Air-Gapped / Sovereign:** The system must operate 100% offline. External APIs (OpenAI, Gemini, Groq) are strictly prohibited in the final pipeline. The `Operating_Mode` config strictly enforces this.
2. **Local LLMs Only:** Inference is handled locally via Ollama. 
   - Text Model: `llama3.2:3b`
   - Vision Model: `moondream`
3. **No Arbitrary Code Execution:** You must NEVER use `subprocess.run`, `os.system`, `exec()`, or `eval()`. All tools must be strictly predefined Python functions (simulations).
4. **Hardware Split:** 
   - **Sitanshu** has an RTX 3050 (6GB VRAM) GPU and will handle all Ollama/Engine inference tasks.
   - **Rohit** has CPU only, and will handle RAG (FastEmbed runs on CPU), DB CRUD, and UI.

---

## 2. Current State (Phases 1, 2, 3, 4, and 6 are COMPLETE)

The following phases are **100% complete, verified, and merged into `main`**:
*   ✅ **Phase 1 (Foundation):** FastAPI server (`src/cognishift/app/main.py`), Pydantic settings (`config.py`).
*   ✅ **Phase 2 (Database Layer):** Async SQLite (`database.py`, `models.py`) with all 8 tables, WAL mode, foreign key enforcement, and workspace/agent CRUD APIs.
*   ✅ **Phase 3 (Providers):** `providers.py`, `ollama_provider.py`, and `simulated_provider.py` implementing sovereign local and mock LLM interfaces.
*   ✅ **Phase 4 (Knowledge Pipeline - Rohit):** Page-aware PDF ingestion, FastEmbed embeddings, ChromaDB vector store, and `/api/v1/knowledge` CRUD in `retriever.py` and `knowledge.py`.
*   ✅ **Phase 6 (Tools & Approvals - Rohit):** Deterministic MRPL industrial tool simulations (`tools.py`) and supervisor approval inbox (`approvals.py`).
*   ✅ **Operator Console UI:** Interactive web operator console in `app/static/index.html`.

---

## 3. Team Sequence & Active Focus

1. **Step 1 (Rohit's Turn - DONE):** Built Phase 4 (Knowledge Pipeline) and Phase 6 (Tools & Approvals) and merged to `main`.
2. **Step 2 (Sitanshu's Turn - ACTIVE):** Sitanshu and his AI build Phase 5 (Execution Engine: `engine.py` & `runs.py`) on GPU, directly importing Rohit's `retrieve_context` and `execute_tool`. Sitanshu then implements Phase 7 (Multimodal Vision).
3. **Step 3 (Final Polish):** Full team integration and UI polish.

See `AGENTS.md` for strict AI-to-AI handoff contracts.

---

## 4. Deep-Dive Implementation Contracts

To ensure Sitanshu's AI and Rohit's AI don't break each other's code, here are the strict interfaces you must build toward.

### Phase 4: Knowledge Pipeline (Owner: Rohit & Rohit's AI)
**Goal:** Ingest PDFs, chunk them, and store embeddings so the Engine can search them.
**Dependencies:** Use `pypdf` for extraction, `fastembed` for CPU-based local embeddings, and `chromadb` for vector storage.
**Contract Interface:** Rohit's AI must create `src/cognishift/core/retriever.py` with this exact async function signature so Sitanshu's Engine can call it:
```python
# src/cognishift/core/retriever.py
async def retrieve_context(workspace_id: int, query: str, top_k: int = 3) -> str:
    """
    Searches ChromaDB for the given query within the workspace.
    Returns a formatted string of the retrieved chunks and their sources.
    If nothing is found, returns an empty string.
    """
```
**API Endpoints required:** 
- `POST /api/v1/knowledge/upload` (accepts `UploadFile`, workspace_id)
- `GET /api/v1/knowledge?workspace_id=X`

### Phase 5: Execution Engine (Owner: Sitanshu & Sitanshu's AI)
**Goal:** The LangChain/LangGraph orchestration loop.
**Dependencies:** LangChain Core. Must import `retrieve_context` from Rohit's `retriever.py` (mock it if Rohit hasn't built it yet).
**Contract Interface:** Sitanshu's AI must create `src/cognishift/core/engine.py` with this exact signature:
```python
# src/cognishift/core/engine.py
async def execute_agent_run(run_id: int, agent_id: int, workspace_id: int, user_prompt: str) -> dict:
    """
    1. Fetches Agent config from DB.
    2. Calls `await retrieve_context(workspace_id, user_prompt)`.
    3. Prompts the OllamaProvider.
    4. Detects if tool execution is requested. If yes, pauses run for Approval (Phase 6).
    5. Returns final text or tool request state.
    """
```
**API Endpoints required:**
- `POST /api/v1/runs` (creates a run in the DB and triggers `execute_agent_run`)
- `GET /api/v1/runs/{run_id}/events` (fetches the timeline)

### Phase 6: Tools & Approvals (Owner: Rohit & Rohit's AI)
**Goal:** Simulated industrial actions and a human-in-the-loop approval pause.
**Dependencies:** Reads from `tool_definitions` table.
**Contract Interface:** Rohit's AI must expose a tool registry in `src/cognishift/core/tools.py`:
```python
# src/cognishift/core/tools.py
async def execute_tool(tool_name: str, parameters: dict) -> str:
    """Simulates the tool execution and returns a status string."""
```
**API Endpoints required:**
- `GET /api/v1/approvals` (list pending tool requests)
- `POST /api/v1/approvals/{request_id}/approve` (resumes the paused Engine run)
- `POST /api/v1/approvals/{request_id}/reject` 

### Phase 7: Multimodal Vision (Owner: Sitanshu & Sitanshu's AI)
**Goal:** Allow users to upload photos of broken equipment.
**Contract:** Sitanshu's AI will update `ollama_provider.py` to accept base64 image strings and send them to the `moondream` model to generate text descriptions before passing them to the main Engine.

---

## 5. Synchronization Checklist for AIs
Before generating code, AIs should ALWAYS:
1. Use file viewing tools to read `src/cognishift/app/db/models.py` and `database.py` to understand the current schema. Do NOT hallucinate database columns.
2. Respect the boundaries. If you are Sitanshu's AI, do not write the PDF extraction logic. If you are Rohit's AI, do not write the Ollama generation logic. 
3. If you need a function from the other developer's domain, write a "mock" function with the agreed-upon signature so your code can compile, and leave a `# TODO: Wait for Dev X` comment.
