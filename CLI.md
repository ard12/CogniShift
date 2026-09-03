# CogniShift CLI: Terminal Command-Line Interface Reference

> **Standalone Industrial Operator Terminal for the Sovereign On-Premise Agentic AI Workbench**  
> **Module:** `src/cognishift/cli.py` (891 lines) | **Entry Point:** `cli.py` | **Framework:** Typer + Rich  
> **Zero Browser Required** — full feature parity with the FastAPI REST API

---

## Table of Contents

1. [Overview & Design Philosophy](#1-overview--design-philosophy)
2. [Installation & Entry Points](#2-installation--entry-points)
3. [Command Reference](#3-command-reference)
   - [System Status](#31-system-status)
   - [Workspace Management](#32-workspace-management)
   - [Agent Registry](#33-agent-registry)
   - [Knowledge & RAG Pipeline](#34-knowledge--rag-pipeline)
   - [Plant Topology Graph](#35-plant-topology-graph)
   - [SCADA Telemetry & SAP PM](#36-scada-telemetry--sap-pm)
   - [Agent Execution (Runs)](#37-agent-execution-runs)
   - [Four-Eyes Safety Approvals](#38-four-eyes-safety-approvals)
   - [Interactive Chat (REPL)](#39-interactive-chat-repl)
4. [Architecture & Technical Details](#4-architecture--technical-details)
5. [Terminal Output Examples](#5-terminal-output-examples)

---

## 1. Overview & Design Philosophy

CogniShift CLI is a **standalone, zero-dependency terminal interface** that provides complete access to every feature of the Sovereign On-Premise Agentic AI Workbench directly from PowerShell, Command Prompt, or any terminal emulator. It is designed for:

- **Field Operators:** SSH-ing into headless edge servers at Purdue Level 3 where no browser is available.
- **Board Operators:** Running quick sensor checks and approval sign-offs without navigating a web dashboard.
- **System Administrators:** Verifying air-gap sovereignty, GPU health, and database statistics from scripts and automation pipelines.
- **Demonstration & Evaluation:** Showcasing the complete CogniShift workflow in a single terminal window during SIH qualifier presentations.

### Key Design Principles

| Principle | Implementation |
|:---|:---|
| **100% Air-Gapped** | All commands execute locally via Ollama + SQLite + ChromaDB. Zero network egress. |
| **Rich Terminal UI** | Powered by [Rich](https://rich.readthedocs.io/) for styled tables, panels, spinners, and color-coded status badges. |
| **Async-Native** | All database and inference calls use `asyncio` with proper `asyncio.to_thread` offloading for CPU-bound operations. |
| **UTF-8 Safe** | Automatic `stdout`/`stderr` UTF-8 reconfiguration on Windows to prevent encoding errors. |
| **Feature Complete** | Every REST API endpoint has a corresponding CLI command. |

---

## 2. Installation & Entry Points

### Prerequisites
The CLI shares the same dependencies as the main workbench. No additional packages required:
```
typer        (CLI framework)
rich         (Terminal rendering)
```
Both are already included in `requirements.txt`.

### Running the CLI

```bash
# Option 1: Root entry point (recommended)
python cli.py [COMMAND]

# Option 2: Python module invocation
python -m cognishift [COMMAND]

# Option 3: Show all available commands
python cli.py --help
```

### Default Behavior
Running `python cli.py` without any command launches the **Interactive Chat REPL** automatically.

---

## 3. Command Reference

### Command Tree

```
cognishift
├── status              System health, GPU, database diagnostics
├── chat                Interactive operator REPL session
│
├── workspace
│   ├── list            List all segregated workspaces
│   └── create          Provision a new workspace
│
├── agent
│   ├── list            List registered agents
│   └── info            View agent configuration details
│
├── knowledge
│   ├── list            List ingested PDF manuals
│   ├── upload          Ingest and embed a PDF manual
│   └── search          Vector RAG search with citations
│
├── graph
│   ├── query           Multi-hop plant topology traversal
│   └── stats           Node/edge type statistics
│
├── telemetry
│   ├── check           Read a specific SCADA sensor
│   ├── stream          Stream all TEP telemetry points
│   └── orders          List SAP PM maintenance orders
│
├── run
│   ├── execute         Execute autonomous agent reasoning
│   ├── history         View past execution runs
│   ├── events          Stream event sourcing timeline
│   └── resume          Resume a paused run
│
└── approvals
    ├── list            List pending HITL requests
    ├── approve         Authorize a high-risk action
    └── reject          Reject a hazardous action
```

---

### 3.1. System Status

```bash
python cli.py status
```

Inspects local GPU health, Ollama model availability, database table row counts, and air-gap sovereignty enforcement. Displays:
- Operating mode (LOCAL / enforced zero-cloud)
- Database engine (SQLite WAL mode path)
- Vector engine (ChromaDB + FastEmbed model)
- Ollama inference status (ONLINE/OFFLINE) with GPU detection
- Available local models (e.g. `llama3.2:3b`, `moondream:latest`)
- Row counts for all 8 core tables

---

### 3.2. Workspace Management

| Command | Description |
|:---|:---|
| `python cli.py workspace list` | List all segregated refinery workspaces with ID, name, description, mode, and creation date. |
| `python cli.py workspace create "CDU-2 Operations" --desc "Crude Distillation Unit 2"` | Provision a new isolated workspace. |

**Options for `workspace create`:**

| Argument / Option | Type | Required | Default | Description |
|:---|:---:|:---:|:---:|:---|
| `NAME` | Argument | Yes | — | Name of the new workspace |
| `--desc`, `-d` | Option | No | `""` | Description of the refinery unit |

---

### 3.3. Agent Registry

| Command | Description |
|:---|:---|
| `python cli.py agent list` | List all agents showing ID, workspace, model, HITL gate status, and activity state. |
| `python cli.py agent list --workspace 1` | Filter agents by workspace ID. |
| `python cli.py agent info 1` | View full configuration for agent #1 including system instructions and allowed tools. |

**Options for `agent list`:**

| Option | Type | Default | Description |
|:---|:---:|:---:|:---|
| `--workspace`, `-w` | int | None | Filter by workspace ID |

**Arguments for `agent info`:**

| Argument | Type | Required | Description |
|:---|:---:|:---:|:---|
| `AGENT_ID` | int | Yes | Agent definition ID to inspect |

---

### 3.4. Knowledge & RAG Pipeline

| Command | Description |
|:---|:---|
| `python cli.py knowledge list` | List all ingested PDF manuals with chunk counts and processing status. |
| `python cli.py knowledge upload "path/to/manual.pdf"` | Ingest a PDF, compute FastEmbed vectors, and store in ChromaDB. |
| `python cli.py knowledge search "MAWP pressure limit"` | Perform vector retrieval with exact `[Filename \| Page X]` citations. |

**Options for `knowledge upload`:**

| Argument / Option | Type | Required | Default | Description |
|:---|:---:|:---:|:---:|:---|
| `FILE_PATH` | Argument | Yes | — | Path to PDF manual file |
| `--workspace`, `-w` | Option | No | `1` | Target workspace ID |
| `--name`, `-n` | Option | No | File stem | Friendly display name for the manual |

**Options for `knowledge search`:**

| Argument / Option | Type | Required | Default | Description |
|:---|:---:|:---:|:---:|:---|
| `QUERY` | Argument | Yes | — | Natural language query to search against manuals |
| `--workspace`, `-w` | Option | No | `1` | Workspace ID |
| `--top-k`, `-k` | Option | No | `3` | Number of top chunks to retrieve |

---

### 3.5. Plant Topology Graph

| Command | Description |
|:---|:---|
| `python cli.py graph query Pump-101A` | Multi-hop traversal of ISO 15926 plant topology for the given equipment tag. |
| `python cli.py graph query Reactor-B --hops 3` | Expand traversal depth to 3 hops. |
| `python cli.py graph stats` | View node entity types (equipment, sensor, valve) and edge relation types (FEEDS_INTO, HAS_SENSOR, etc.). |

**Options for `graph query`:**

| Argument / Option | Type | Required | Default | Description |
|:---|:---:|:---:|:---:|:---|
| `TAG` | Argument | Yes | — | Equipment tag or keyword (e.g., `Pump-101A`, `Reactor-B`, `SV-402`) |
| `--workspace`, `-w` | Option | No | `1` | Workspace ID |
| `--hops` | Option | No | `2` | Max relationship traversal hops |

---

### 3.6. SCADA Telemetry & SAP PM

| Command | Description |
|:---|:---|
| `python cli.py telemetry check PT-101` | Read a specific sensor from TEP SCADA stream. Auto-detects pressure (`PT-*`) vs temperature (`TT-*`). |
| `python cli.py telemetry stream` | Display all Tennessee Eastman Process telemetry points across nominal and fault scenarios. |
| `python cli.py telemetry orders` | List SAP S/4HANA PM work orders with notification type, damage code, and completion status. |

**Arguments for `telemetry check`:**

| Argument | Type | Required | Description |
|:---|:---:|:---:|:---|
| `SENSOR_ID` | str | Yes | Instrument sensor tag (e.g., `PT-101`, `TT-204`) |

---

### 3.7. Agent Execution (Runs)

| Command | Description |
|:---|:---|
| `python cli.py run execute "Check pressure on PT-101"` | Execute an autonomous reasoning run on the local GPU. |
| `python cli.py run execute "Inspect gauge" --image "photo.png"` | Execute with multimodal vision (local Moondream VLM). |
| `python cli.py run history` | View past execution runs with status badges. |
| `python cli.py run events 67` | Stream the immutable event-sourcing audit timeline for run #67. |
| `python cli.py run resume 42` | Resume a paused run after supervisor approval. |

**Options for `run execute`:**

| Argument / Option | Type | Required | Default | Description |
|:---|:---:|:---:|:---:|:---|
| `PROMPT` | Argument | Yes | — | Natural language instruction for the agent |
| `--agent`, `-a` | Option | No | `1` | Agent definition ID |
| `--workspace`, `-w` | Option | No | `1` | Workspace ID |
| `--image`, `-i` | Option | No | None | Path to a field photo for multimodal VLM inspection |
| `--user`, `-u` | Option | No | `"operator"` | Operator employee ID for audit trail |

**Options for `run history`:**

| Option | Type | Default | Description |
|:---|:---:|:---:|:---|
| `--workspace`, `-w` | int | `1` | Workspace ID |
| `--limit`, `-l` | int | `10` | Number of past runs to retrieve |

---

### 3.8. Four-Eyes Safety Approvals

| Command | Description |
|:---|:---|
| `python cli.py approvals list` | List all pending supervisor authorization requests. |
| `python cli.py approvals approve 16` | Sign off request #16 and automatically resume the paused run. |
| `python cli.py approvals approve 16 --reviewer EMP-8921` | Sign off with a specific supervisor employee ID. |
| `python cli.py approvals reject 16` | Reject request #16 and cancel the associated run. |

**Options for `approvals approve` / `approvals reject`:**

| Argument / Option | Type | Required | Default | Description |
|:---|:---:|:---:|:---:|:---|
| `REQUEST_ID` | Argument | Yes | — | Approval request ID |
| `--reviewer`, `-r` | Option | No | `"SUPERVISOR-3410"` | Supervisor employee ID for audit trail |

---

### 3.9. Interactive Chat (REPL)

```bash
python cli.py chat
python cli.py chat --workspace 2 --agent 1
```

Launches a **persistent interactive operator session** with a styled prompt, real-time spinners during inference, and built-in slash commands:

| Slash Command | Action |
|:---|:---|
| `/image <path>` | Attach a photo for multimodal VLM inspection on the next query |
| `/image` | Clear any attached image |
| `/status` | Display system health and GPU diagnostics |
| `/approvals` | View pending Four-Eyes safety requests |
| `/approve <id>` | Digitally sign off a pending approval request |
| `/telemetry` | Stream all live SCADA sensor readings |
| `/clear` | Clear the terminal screen |
| `/exit` | Exit the interactive session |
| `exit` or `quit` | Alternative exit commands |

**Keyboard shortcuts:** `Ctrl+C` or `Ctrl+D` gracefully exit the session.

---

## 4. Architecture & Technical Details

### Module Structure

```
CogniShift/
├── cli.py                          # Root entry point (adds src/ to sys.path)
├── src/
│   └── cognishift/
│       ├── __main__.py             # Enables `python -m cognishift`
│       └── cli.py                  # Full CLI implementation (891 lines)
```

### Technology Stack

| Component | Technology | Purpose |
|:---|:---|:---|
| CLI Framework | **Typer** | Declarative command/argument/option definitions with auto-generated `--help` |
| Terminal Rendering | **Rich** | Styled tables, panels, spinners, color-coded badges, and progress indicators |
| Async Bridge | `asyncio.run()` | Bridges Typer's synchronous command handlers with the async database/engine layer |
| Encoding | `sys.stdout.reconfigure(encoding="utf-8")` | Windows console UTF-8 compatibility |

### Data Flow

```
Terminal Input
     │
     ▼
[Typer Command Parser]
     │
     ▼
[asyncio.run() Bridge]
     │
     ├──► [aiosqlite] ──► SQLite WAL Database
     ├──► [ChromaDB]  ──► Vector Store (FastEmbed)
     ├──► [Ollama]    ──► Local GPU LLM/VLM Inference
     └──► [tools.py]  ──► Industrial SCADA / SAP PM Data
     │
     ▼
[Rich Renderer] ──► Styled Terminal Output
```

---

## 5. Terminal Output Examples

### System Status

```
+-----------------------------------------------------------------------------+
| COGNISHIFT v0.1.0 | Sovereign On-Premise Agentic AI Workbench               |
| MRPL Industrial Operations | IEC 62443 Level 3.5 | Air-Gapped Zero-Cloud    |
+-----------------------------------------------------------------------------+
                       System & Sovereignty Diagnostics
+-----------------------------------------------------------------------------+
| Component        | Status / Setting            | Details                    |
|------------------+-----------------------------+----------------------------|
| Operating Mode   | LOCAL                       | Strict zero cloud egress   |
| Ollama Inference | ONLINE (GPU)                | http://localhost:11434     |
| Text Model       | llama3.2:3b                 | Primary reasoning SLM      |
| Vision Model     | moondream                   | Gauge inspection & OCR VLM |
+-----------------------------------------------------------------------------+
```

### Agent Execution with Multimodal Vision

```
>>> Initiating Agent Run (Workspace #1, Agent #1)...
[IMAGE] Multimodal Input Attached: gauge_pressure_nominal_105psi.png
┌────────────────────── Run #67 Response (llama3.2:3b) ───────────────────────┐
│ Status: COMPLETED                                                           │
│                                                                             │
│ **Pressure Dial Inspection Report**                                         │
│                                                                             │
│ The analog pressure dial has been inspected, and the current reading is     │
│ 105.2 PSI. The reading is within the Normal Operating Range of 80-120 PSI.  │
│                                                                             │
│ Citations: MRPL_MEGA_CORPUS_500P.pdf | Page 395 + Local VLM Inspection      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Event Sourcing Audit Timeline

```
                       Event Sourcing Timeline: Run #67
┌────────────────────────┬─────────────────────────────┬──────────────────────┐
│ Event Type             │ Message / State Mutation    │ Timestamp            │
├────────────────────────┼─────────────────────────────┼──────────────────────┤
│ run_started            │ Run initiated for agent     │ 2026-09-03 10:30:26  │
│ vision_started         │ Analyzing image...          │ 2026-09-03 10:30:26  │
│ vision_completed       │ Visual inspection completed │ 2026-09-03 10:30:31  │
│ retrieval_completed    │ Retrieved context (3 cites) │ 2026-09-03 10:30:32  │
│ model_response         │ Model reasoning received    │ 2026-09-03 10:30:33  │
│ tool_executed          │ PT-101: 105.2 PSI NOMINAL   │ 2026-09-03 10:30:33  │
│ completed              │ Run completed successfully  │ 2026-09-03 10:30:36  │
└────────────────────────┴─────────────────────────────┴──────────────────────┘
```

### Four-Eyes HITL Safety Interception

```
┌──────────────────── Run #38: PAUSED AT HITL GATE ───────────────────────┐
│ [HITL GATE] SAFETY INTERLOCK TRIGGERED (Four-Eyes Principle)             │
│                                                                         │
│ Execution is PAUSED awaiting Shift Supervisor authorization.            │
│                                                                         │
│ Action: emergency_pressure_relief on Reactor-B                          │
│ Run ID: 38                                                              │
│                                                                         │
│ To authorize: run `python cli.py approvals approve <request_id>`        │
└─────────────────────────────────────────────────────────────────────────┘
```
