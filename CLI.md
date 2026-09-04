# CogniShift CLI: Terminal Interface Reference

Standalone terminal command-line interface for the CogniShift on-premise workbench.

* **Module:** `src/cognishift/cli.py`
* **Entry Point:** `cli.py`
* **Framework:** Typer + Rich
* **No Browser Required:** Full feature parity with the REST API for headless edge servers and SSH sessions.

---

## 1. Overview

CogniShift CLI provides complete terminal access to every workbench capability directly from PowerShell, Command Prompt, or Linux terminals:
* **Local Operation:** Commands interact with local SQLite, ChromaDB, and Ollama services.
* **Rich Formatting:** Uses Rich for formatted tables, panels, spinners, and status indicators.
* **Asynchronous Integration:** Bridges Typer's command handlers with the underlying async engine using `asyncio.run()`.
* **UTF-8 Compatibility:** Reconfigures Windows terminal output to UTF-8 to prevent encoding issues.

---

## 2. Usage & Entry Points

```bash
# Direct entry point
python cli.py [COMMAND]

# Python module invocation
python -m cognishift [COMMAND]

# Command help
python cli.py --help

# Launch interactive chat session (default when run without arguments)
python cli.py
```

---

## 3. Command Reference

### Command Hierarchy

```
cognishift
├── status              System diagnostics and local model status
├── chat                Interactive operator REPL session
│
├── workspace
│   ├── list            List all workspaces
│   └── create          Create a new workspace
│
├── agent
│   ├── list            List registered agents
│   └── info            View agent details and instructions
│
├── knowledge
│   ├── list            List ingested documents
│   ├── upload          Ingest and embed a PDF document
│   └── search          Vector search with page citations
│
├── graph
│   ├── query           Traverse equipment topology
│   └── stats           View node and edge counts
│
├── telemetry
│   ├── check           Read a specific simulated sensor
│   ├── stream          Display simulated SCADA stream
│   └── orders          List synthetic SAP PM work orders
│
├── run
│   ├── execute         Run agent reasoning on prompt (optional --image)
│   ├── history         View previous runs
│   ├── events          Display event log for a run
│   └── resume          Resume an approved run
│
└── approvals
    ├── list            List pending approval requests
    ├── approve         Approve a pending request
    └── reject          Reject a pending request
```

---

### 3.1. System Status
```bash
python cli.py status
```
Displays system diagnostics:
* Operating mode (local configuration)
* SQLite database file path and WAL mode status
* ChromaDB vector storage directory
* Ollama local service availability
* Available local models (e.g., `llama3.2:3b`, `moondream:latest`)
* Row counts for core database tables

---

### 3.2. Workspace Commands
* `python cli.py workspace list`: List all workspaces with IDs, names, and operating modes.
* `python cli.py workspace create "CDU-2 Operations" --desc "Crude Distillation Unit 2"`: Create a new workspace.

---

### 3.3. Agent Commands
* `python cli.py agent list`: List all registered agents.
* `python cli.py agent list --workspace 1`: Filter agents by workspace ID.
* `python cli.py agent info 1`: Display configuration details, system prompt, and allowed tools for agent #1.

---

### 3.4. Knowledge & Retrieval Commands
* `python cli.py knowledge list`: List ingested PDF documents with chunk counts and status.
* `python cli.py knowledge upload "path/to/manual.pdf"`: Ingest a PDF, generate embeddings with FastEmbed, and store in ChromaDB.
* `python cli.py knowledge search "maximum pressure"`: Perform vector search and print text chunks with `[Filename | Page X]` citations.

---

### 3.5. Plant Topology Graph Commands
* `python cli.py graph query Pump-101A`: Search equipment topology graph starting from a tag name.
* `python cli.py graph query Reactor-B --hops 3`: Traverse up to 3 hops of relationships.
* `python cli.py graph stats`: Show counts of node types (equipment, sensors, valves) and edge types (`FEEDS_INTO`, `PROTECTED_BY`).

---

### 3.6. Simulated SCADA Telemetry & Maintenance Commands
* `python cli.py telemetry check PT-101`: Read simulated sensor value for a specific tag.
* `python cli.py telemetry stream`: View simulated Tennessee Eastman Process sensor readings.
* `python cli.py telemetry orders`: View synthetic SAP PM maintenance work orders.

---

### 3.7. Agent Runs
* `python cli.py run execute "Check pressure on PT-101"`: Run agent reasoning on the local model.
* `python cli.py run execute "Inspect dial" --image "gauge.png"`: Run agent reasoning with visual input via local Moondream.
* `python cli.py run history`: View past runs and statuses (`completed`, `paused`, `failed`).
* `python cli.py run events <run_id>`: Display chronological event sourcing log for a run.
* `python cli.py run resume <run_id>`: Resume a run that was paused for supervisor approval.

---

### 3.8. Human-in-the-Loop Approvals
* `python cli.py approvals list`: List pending approval requests awaiting review.
* `python cli.py approvals approve <id>`: Record approval for a request and resume the run.
* `python cli.py approvals approve <id> --reviewer EMP-1042`: Specify reviewer identifier.
* `python cli.py approvals reject <id>`: Reject an action and mark the run as cancelled.

---

### 3.9. Interactive Chat (REPL)
```bash
python cli.py chat
python cli.py chat --workspace 1 --agent 1
```
Launches an interactive operator session supporting slash commands:
* `/image <path>`: Attach an image for multimodal inspection.
* `/status`: Display system and model status.
* `/approvals`: View pending approval requests.
* `/approve <id>`: Approve a pending request.
* `/telemetry`: Display simulated sensor stream.
* `/clear`: Clear the terminal screen.
* `/exit`: Exit the session.
