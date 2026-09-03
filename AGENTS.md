# Agentic Alignment Guide (AI to AI Handoff)

> **HELLO FELLOW AI ASSISTANT!** 👋
> If you are reading this, you are likely assisting Rohit in building the next phase of the CogniShift platform. I am the AI assistant helping Sitanshu. To make sure our code integrates perfectly, please read this situation report carefully.

---

## 1. Our Situation & Constraints

We are building a **Sovereign On-Premise Agentic AI Workbench** (SIH26117).
*   **Zero Cloud:** The system must operate 100% offline. Do not add code that requires external APIs like OpenAI or Gemini.
*   **Security:** Do not use `subprocess.run` or arbitrary command execution anywhere.
*   **What is done:** I have already built the FastAPI backend, the async SQLite database, the agent CRUD routes, and the local `OllamaProvider`. Check `src/cognishift/app/db/models.py` and `database.py` to see the current schema.

## 2. The Game Plan

Because Sitanshu has a GPU, he (and I) will build the AI Execution Engine loop that runs inference. Because Rohit has a CPU, you two will build the Platform APIs (which only require CPU).

We are working sequentially. **It is your turn first.**

You need to build the Knowledge Pipeline and the Tool Approval endpoints. Once you push your code to `main`, I will read it and build the Engine that imports your functions.

---

## 3. Your Specific Tasks (What you must build)

Please execute the following tasks. Do not build the Execution Engine (Phase 5) — leave that for me.

### Task A: Phase 4 (Knowledge Pipeline)
1. **Dependencies:** Use `pypdf` for text extraction, `fastembed` for CPU-based local embeddings, and `chromadb` for local vector storage.
2. **Endpoints:** Build `POST /api/v1/knowledge/upload` (accepts PDF and `workspace_id`) and `GET /api/v1/knowledge` in `src/cognishift/app/api/knowledge.py`.
3. **The Contract:** You MUST export the following async function in `src/cognishift/core/retriever.py` so that I can call it later:
   ```python
   async def retrieve_context(workspace_id: int, query: str, top_k: int = 3) -> str:
       """
       Searches ChromaDB for the given query within the workspace.
       Returns a formatted string containing the text chunks and source citations.
       """
   ```

### Task B: Phase 6 (Tools & Approvals)
1. **Endpoints:** Build the Human-in-the-Loop API in `src/cognishift/app/api/approvals.py`. You need endpoints to list pending `approval_requests`, and `POST` endpoints to approve/reject them.
2. **The Contract:** You MUST export a tool registry in `src/cognishift/core/tools.py` so my Engine knows what tools exist:
   ```python
   async def execute_tool(tool_name: str, parameters: dict) -> str:
       """
       Simulates the execution of the tool (e.g. check_pressure) and returns a text result.
       """
   ```

## 4. Current Status: Handoff Received! 🤝

**Rohit and his AI assistant have successfully completed Task A (Phase 4) and Task B (Phase 6)!**
- Commit `26a8c60` merged cleanly.
- `retrieve_context` and `execute_tool` contracts verified.
- **Sitanshu and his AI assistant are now actively building Phase 5 (The Execution Engine in `core/engine.py` and `app/api/runs.py`).**

