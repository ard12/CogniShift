# CogniShift Deep Technical Audit Report & Architectural Remediation Roadmap

**Document Version:** 2.0.0 (Deep Inspection Edition)  
**Target Branch:** `fix/audit-remediation`  
**Date:** September 5, 2026  
**Scope:** Full codebase audit covering concurrency, state machines, API routes, database schemas, LLM tool-calling pipelines, security boundaries, performance bottlenecks, CLI mechanics, and test integrity.

---

## Executive Summary

An exhaustive, line-by-line technical audit was executed across the **CogniShift** repository. This audit examined the interactions between the FastAPI ASGI application, local SQLite (aiosqlite) WAL database, ChromaDB vector substrate, Ollama inference providers, the autonomous reasoning engine, and the Rich/Typer terminal CLI.

The audit uncovered **13 technical findings**:
* **2 Critical Defects:** Broken CLI exports causing fatal `ImportError` on startup, and missing CLI runtime dependencies in `requirements.txt`.
* **3 High-Severity Concurrency & State Machine Defects:** Double-execution race conditions in approvals resumption, transaction uncommitted task scheduling, and state machine status divergence (`cancelled` vs `completed`).
* **4 Medium-Severity Tool Calling & Security Defects:** Empty tool schemas preventing typed LLM arguments, network/Ollama error masking as successful runs, image path traversal perimeter blocking benchmark test images, and lack of hybrid JSON tool fallback for quantized SLMs.
* **4 Performance, Scalability & Resilience Findings:** Missing database indexes on high-frequency tables, blocking synchronous vector deletion on the event loop, missing air-gap fallback for text splitting, and residual hardcoded operator identifiers.

---

## 1. Master Findings Matrix

| ID | Severity | Category | Component | Root Cause Summary | Operational Impact |
|:---|:---|:---|:---|:---|:---|
| **DEF-01** | **High** | Concurrency | `app/api/approvals.py` & `engine.py` | Double resumption without atomic state lock | Web UI triggers approval task + HTTP resume concurrently; risk of executing hazardous safety tools twice. |
| **DEF-02** | **High** | Concurrency | `app/api/approvals.py` | `asyncio.create_task` scheduled before `db.commit()` | Background resumption queries uncommitted DB state, reading `pending` and failing with `ValueError`. |
| **DEF-03** | **High** | State Machine | `cli.py` vs `engine.py` | Status divergence on rejection (`cancelled` vs `completed`) | CLI rejection sets `cancelled` without event logging; REST API sets `completed` with audit log. Tests break. |
| **DEF-04** | **Critical** | Runtime Integrity | `core/tools.py` & `cli.py` | Telemetry loaders not re-exported after plugin extraction | `cognishift` CLI crashes immediately on startup with `ImportError`. |
| **DEF-05** | **Critical** | Dependencies | `requirements.txt` & `Dockerfile` | Missing `typer` and `rich` in dependencies | Clean Docker container or fresh developer setup crashes when running the CLI workbench. |
| **DEF-06** | **Medium** | Tool Calling | `seed.py` & `database.py` | Default tools have empty `{}` schemas | Ollama models receive no parameter specifications; cannot generate typed arguments; forces hardcoded fallbacks. |
| **DEF-07** | **Medium** | Error Handling | `ollama_provider.py` & `engine.py` | Offline Ollama errors treated as successful runs | Model timeout/refusal strings saved as `status='completed'`, masking infrastructure failures from operators. |
| **DEF-08** | **Medium** | Model Resilience | `core/engine.py` | Tool detection relies strictly on native `tool_calls` | Quantized local models (Llama 3.2 3B) emitting markdown JSON blocks in text are ignored and tool intent lost. |
| **DEF-09** | **Medium** | Security Boundary | `core/engine.py` | `input_image_path` restricted strictly to `upload_dir` | Vision benchmarks in `data/vision_test/` rejected by security perimeter check. |
| **DEF-10** | **Medium** | Performance | `db/database.py` | Zero B-Tree indexes on relational tables | High-frequency telemetry runs and events trigger full table scans on every query. |
| **DEF-11** | **Low** | Performance | `api/knowledge.py` | Synchronous ChromaDB deletion blocks ASGI event loop | Large manual deletions freeze HTTP request handling for other operators. |
| **DEF-12** | **Low** | Air-Gap Resilience | `core/retriever.py` | Hard dependency on `langchain_text_splitters` | Air-gapped environments without the external package fail to import RAG modules. |
| **DEF-13** | **Low** | Code Quality | `static/index.html` | Hardcoded operator username `"operator_sitanshu"` | Audit trails attribute all Web UI actions to a single hardcoded identity. |

---

## 2. In-Depth Technical Analysis & Root Cause Breakdown

---

### Finding DEF-01: Double Execution & Non-Atomic Resumption Race Condition

#### Mechanism & Code Path
When an operator authorizes a gated action in the Web UI, `executeApproval` in `src/cognishift/app/static/index.html` executes two consecutive asynchronous HTTP calls:
```javascript
// src/cognishift/app/static/index.html:523-529
await fetch(`${API_BASE}/approvals/${approvalId}/${action}`, { method: 'POST' });
fetchApprovals();

if (runId) {
    const res = await fetch(`${API_BASE}/runs/${runId}/resume`, { method: 'POST' });
    if (res.ok) {
        const resumedRun = await res.json();
        renderRunOutcome(resumedRun);
    }
}
```
1. The first request (`POST /api/v1/approvals/{id}/approve`) spawns a background task via `asyncio.create_task(resume_agent_run(run_id))`.
2. The second request immediately calls `POST /api/v1/runs/{run_id}/resume`, which directly invokes `await resume_agent_run(run_id)`.

Now examine `resume_agent_run` in `src/cognishift/core/engine.py`:
```python
# src/cognishift/core/engine.py:369-376
cursor = await db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
run_row = await cursor.fetchone()
run = dict(run_row)

if run["status"] != "paused":
    raise ValueError(f"Run {run_id} is not paused (current status: '{run['status']}')")
```

#### The Failure Modes:
* **Race Mode A (Double Tool Execution):** If both coroutines read `agent_runs` before either commits the final update, both pass `status != "paused"`. Both proceed to line 404 (`tool_output = await execute_tool(tool_name, params)`). In a refinery setting, this executes a physical safety relief valve or pump restart **twice**.
* **Race Mode B (Unhandled 400 Bad Request):** If the background task finishes first, the second HTTP request hits `if run["status"] != "paused"`, raising a `ValueError`. FastAPI converts this to a `400 Bad Request`. In the browser, `res.ok` is false, `renderRunOutcome` is skipped, and the UI never displays the final incident report.

#### Remediation Specification
Implement an **atomic compare-and-swap** transition using SQL:
```python
# In src/cognishift/core/engine.py -> resume_agent_run()
async with get_db() as db:
    # Atomic transition from 'paused' to 'resuming'
    cursor = await db.execute(
        """UPDATE agent_runs 
           SET status = 'resuming' 
           WHERE id = ? AND status = 'paused' 
           RETURNING *""",
        (run_id,)
    )
    claimed_run = await cursor.fetchone()
    
    if not claimed_run:
        # Check if another task already completed this run
        cursor = await db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
        existing = await cursor.fetchone()
        if existing and existing["status"] == "completed":
            logger.info(f"Run {run_id} is already completed. Returning existing run record.")
            return RunResponse.model_validate(dict(existing))
        raise ValueError(f"Run {run_id} is not paused (current status: '{existing['status'] if existing else 'not_found'}')")
    
    run = dict(claimed_run)
    await db.commit()
```

---

### Finding DEF-02: Asynchronous Task Dispatch Before Database Commit

#### Mechanism & Code Path
In `src/cognishift/app/api/approvals.py`:
```python
# src/cognishift/app/api/approvals.py:37-49
cursor = await db.execute(
    """UPDATE approval_requests 
       SET status = 'approved', reviewed_by = 'human_supervisor', reviewed_at = ? 
       WHERE id = ? RETURNING *""",
    (now, request_id)
)
updated_row = await cursor.fetchone()

# Spawn background resume task BEFORE commit
asyncio.create_task(resume_agent_run(updated_row["run_id"]))

await db.commit()
return ApprovalResponse.model_validate(dict(updated_row))
```

#### The Failure Mode
`asyncio.create_task` posts `resume_agent_run` directly to the event loop. `resume_agent_run` immediately calls `get_db()`, acquiring its own connection and querying:
```python
SELECT * FROM approval_requests WHERE run_id = ? ORDER BY requested_at DESC LIMIT 1
```
If the event loop yields control to `resume_agent_run` before `await db.commit()` completes on the first connection, SQLite's WAL isolation will return `status = 'pending'`, triggering:
```python
if approval["status"] == "pending":
    raise ValueError(f"Approval request {approval['id']} is still pending supervisor decision.")
```
The entire resumption crashes silently in the background task.

#### Remediation Specification
Move `await db.commit()` immediately after fetching the updated row, prior to dispatching `asyncio.create_task`:
```python
updated_row = await cursor.fetchone()
await db.commit()

# Safe to dispatch now that database state is persisted
asyncio.create_task(resume_agent_run(updated_row["run_id"]))
```

---

### Finding DEF-03: Divergent State Machine Status on Rejection (`cancelled` vs `completed`)

#### Mechanism & Code Path
When a supervisor rejects an action:
* **In CLI (`cli.py:763-768`):**
  ```python
  await db.execute("UPDATE agent_runs SET status = 'cancelled', result_text = 'Action rejected by supervisor.' ...")
  ```
  No event is logged to `run_events`.
* **In Engine (`engine.py:438-448`):**
  ```python
  await db.execute("UPDATE agent_runs SET status = 'completed', result_text = ? ...")
  await log_event(db, run_id, "rejected", f"Action '{tool_name}' rejected by supervisor.")
  ```
* **In Automated Tests (`test_engine.py:199-201`):**
  ```python
  resumed = await resume_agent_run(run_id=run_res.id)
  assert resumed.status == "completed"
  assert "rejected" in resumed.result_text.lower()
  ```

#### The Failure Mode
If a run is rejected via CLI, `agent_runs.status` becomes `'cancelled'`, which violates the test assertions and the standard schema expectations. Furthermore, because `cli.py` bypasses `log_event`, the event timeline (`/runs/{id}/events`) has no record of who rejected the action or why.

#### Remediation Specification
In `src/cognishift/cli.py`, invoke `resume_agent_run(run_id)` for rejections (after marking the request as `'rejected'`), unifying all state mutations under the central engine.

---

### Finding DEF-04 & DEF-05: Critical Packaging, Import & Dependency Failures

#### Missing Re-Exports (`core/tools.py`)
Moving `load_tep_telemetry`, `load_maintenance_orders`, and `load_refinery_topology` to `plugins/simulation/tep_tools.py` leaves `src/cognishift/cli.py` broken with:
```text
ImportError: cannot import name 'load_tep_telemetry' from 'cognishift.core.tools'
```
**Fix:** Re-export these functions in `src/cognishift/core/tools.py`.

#### Missing CLI Dependencies (`requirements.txt`)
`requirements.txt` lacks `typer` and `rich`. Clean containers built via `Dockerfile` will crash with:
```text
ModuleNotFoundError: No module named 'typer'
```
**Fix:** Add `typer>=0.9.0` and `rich>=13.0.0` to `requirements.txt`.

---

### Finding DEF-06: Empty Tool Schemas Preventing Typed LLM Function Arguments

#### Mechanism & Code Path
In `src/cognishift/core/engine.py:228-244`:
```python
ollama_tools = []
for t in available_tools:
    schema = json.loads(t.get("input_schema", "{}"))
    if "type" not in schema:
        schema = {"type": "object", "properties": schema}
    ollama_tools.append({
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": schema
        }
    })
```
In `scripts/seed.py`, tools are seeded without `input_schema`, defaulting to `'{}'`. Therefore, Ollama receives:
```json
{
  "name": "check_pressure",
  "parameters": {"type": "object", "properties": {}}
}
```

#### The Failure Mode
The model has no way of knowing what parameters exist (`sensor_id`, `chamber_id`, `valve_tag`). As a result, the model cannot supply structured arguments, emitting empty `{}` parameters and forcing tools to fall back to hardcoded defaults.

#### Remediation Specification
Define explicit JSON schemas in `scripts/seed.py` and `database.py`:
```python
# check_pressure
json.dumps({
    "type": "object",
    "properties": {
        "sensor_id": {"type": "string", "description": "Pressure transmitter tag (e.g. PT-101, PT-400)"}
    },
    "required": ["sensor_id"]
})

# emergency_pressure_relief
json.dumps({
    "type": "object",
    "properties": {
        "chamber_id": {"type": "string", "description": "Unit or reactor chamber tag (e.g. Reactor-B)"},
        "valve_tag": {"type": "string", "description": "Pilot safety valve tag (e.g. SV-402)"}
    },
    "required": ["chamber_id"]
})
```

---

### Finding DEF-07: Unhandled Network/Ollama Errors Masked as "Completed" Runs

#### Mechanism & Code Path
In `src/cognishift/core/ollama_provider.py:52-58`:
```python
except (httpx.ConnectError, httpx.TimeoutException, Exception) as e:
    return ModelResponse(
        text=f"Error communicating with Ollama: {str(e)}",
        model_name=self.text_model,
        provider="ollama",
        is_simulated=False
    )
```
In `src/cognishift/core/engine.py:326-340`:
```python
final_text = model_response.text
cursor = await db.execute(
    """UPDATE agent_runs
       SET status = 'completed', result_text = ?, sources_used = ?, completed_at = CURRENT_TIMESTAMP
       WHERE id = ? RETURNING *""",
    (final_text, sources_used, run_id)
)
```

#### The Failure Mode
When the local Ollama daemon is offline or crashes, the run is marked as `status = 'completed'` with a green badge in the UI and `result_text = "Error communicating with Ollama: Connection refused"`. The `error_message` field in `agent_runs` remains `NULL`.

#### Remediation Specification
Check for provider communication errors and fail the run cleanly:
```python
if model_response.text.startswith("Error communicating with Ollama"):
    cursor = await db.execute(
        """UPDATE agent_runs
           SET status = 'failed', error_message = ?, completed_at = CURRENT_TIMESTAMP
           WHERE id = ? RETURNING *""",
        (model_response.text, run_id)
    )
    updated_run = await cursor.fetchone()
    await db.commit()
    await log_event(db, run_id, "failed", model_response.text)
    return RunResponse.model_validate(dict(updated_run))
```

---

### Finding DEF-08: Hybrid JSON Fallback for Quantized Local Models

Small open-weight models (`llama3.2:3b`) running under 4-bit quantization frequently emit their tool calls inside markdown code blocks:
````text
```json
{
  "tool": "check_pressure",
  "parameters": {"sensor_id": "PT-101"}
}
```
````
If native `tool_calls` is empty, `engine.py` currently treats this as raw text. Adding a secondary JSON block parser ensures that tool intent is never dropped.

---

### Finding DEF-09: Overly Restrictive Image Perimeter Check

`engine.py` line 155 requires:
```python
if not img_path.is_relative_to(upload_dir):
    raise ValueError(...)
```
Official benchmark images reside in `data/vision_test/` (under `settings.data_dir`), not `settings.upload_dir`.
**Remediation:** Check against `settings.data_dir.resolve()` to allow both `uploads/` and `vision_test/` while preserving the directory traversal sandbox.

---

### Finding DEF-10: Database Relational Storage Indexing Deficit

The tables `agent_runs`, `run_events`, `approval_requests`, `graph_edges`, and `knowledge_sources` lack B-Tree indexes. Under continuous plant operation, event sourcing tables grow to tens of thousands of rows.
**Remediation:** Add the following indexes to `src/cognishift/app/db/database.py`:
```sql
CREATE INDEX IF NOT EXISTS idx_agent_runs_ws_time ON agent_runs(workspace_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_events_run ON run_events(run_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_graph_edges_lookup ON graph_edges(workspace_id, source_node_id, target_node_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_ws ON knowledge_sources(workspace_id);
```

---

### Finding DEF-11, DEF-12 & DEF-13: Code Quality, Performance & Portability

1. **Async Offload for ChromaDB Deletion (`DEF-11`):** Wrap `collection.delete(...)` in `asyncio.to_thread` to prevent ASGI event loop blocking.
2. **Resilient Text Splitter Fallback (`DEF-12`):** Provide a `try/except ImportError` around `langchain_text_splitters` with the pure-Python recursive splitter as fallback.
3. **Generalize Web UI Operator Identity (`DEF-13`):** Replace `"operator_sitanshu"` in `index.html` with `"operator"` or a dynamic session identifier.

---

## 3. Prioritized Implementation Plan

### Stage 1: Runtime Integrity & Build Fixes (Immediate)
1. Add `typer` and `rich` to `requirements.txt`.
2. Re-export simulation functions in `src/cognishift/core/tools.py`.
3. Expand image path perimeter in `src/cognishift/core/engine.py`.

### Stage 2: Concurrency & State Machine Hardening
4. Implement atomic compare-and-swap status transition in `resume_agent_run`.
5. Fix commit-before-task sequencing in `src/cognishift/app/api/approvals.py`.
6. Unify rejection handling in `src/cognishift/cli.py` to route through `resume_agent_run`.

### Stage 3: LLM Pipeline & Reliability Enhancements
7. Populate rich JSON input schemas in `scripts/seed.py` and `database.py`.
8. Transition runs to `status = 'failed'` when Ollama is unreachable.
9. Add secondary markdown JSON parser in `engine.py`.

### Stage 4: Database Indexing & Scalability
10. Add B-Tree indexes in `init_db()`.
11. Add `asyncio.to_thread` around ChromaDB deletion in `api/knowledge.py`.
12. Add zero-dependency fallback for `langchain_text_splitters` in `retriever.py`.
13. Generalize operator ID in `index.html`.

---

*Report authored and validated on branch `fix/audit-remediation`.*
