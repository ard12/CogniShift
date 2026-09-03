# CogniShift: Complete Team Guide & Project Encyclopedia

> **Welcome to the CogniShift Team Guide!**  
> This guide explains **what this project is**, **why we are building it**, and **how every single file in the repository works** in plain, everyday language. Whether you are writing backend code, reviewing the architecture, or presenting to hackathon evaluators, this document gives you the complete picture without confusing jargon.

---

## Table of Contents
1. [What is CogniShift? (The Big Picture)](#1-what-is-cognishift-the-big-picture)
2. [How It Works (The 6 Core Stations)](#2-how-it-works-the-6-core-stations)
3. [File-by-File Technical Guide](#3-file-by-file-technical-guide)
4. [Real-World Operational Scenarios](#4-real-world-operational-scenarios)
5. [Presentation Pitch & FAQ Cheat Sheet](#5-presentation-pitch--faq-cheat-sheet)

---

## 1. What is CogniShift? (The Big Picture)

### The Real-World Problem (MRPL Petrochemical Refinery)
**Mangalore Refinery and Petrochemicals Limited (MRPL)** operates complex chemical units (Crude Distillation, Hydrocrackers, Fluid Catalytic Cracking) that process flammable hydrocarbons at extreme pressures (up to 500 PSI) and temperatures (over 450 °C).

When field engineers and board operators manage these units:
1. **Massive Manuals:** Standard operating procedures and HAZOP safety studies span thousands of pages. Searching them manually during an alarm cascade costs critical minutes.
2. **Zero Cloud Tolerance:** Sending plant schematics, maintenance histories, or operational telemetry to commercial clouds (ChatGPT, Gemini, Anthropic) is strictly prohibited due to national critical infrastructure sovereignty and cybersecurity regulations.
3. **Safety Handcuffs (Four-Eyes Principle):** An AI assistant must never have unvetted authority to actuate physical valves or restart high-voltage pump motors. High-risk actions must require a human supervisor's explicit digital sign-off.

### The Solution: CogniShift
CogniShift is a **sovereign, air-gapped agentic workbench** built directly for the plant:
* **100% Offline AI:** Runs local open-weight models (`llama3.2:3b` for reasoning and `moondream` for vision) directly on the refinery's NVIDIA GPU workstations.
* **Hybrid GraphRAG:** Combines page-accurate PDF manual search with a physical **Plant Topology Knowledge Graph** to understand how equipment connects (e.g. Pump P-101A feeds Reactor-B which is protected by Valve SV-402).
* **Multimodal Visual Inspection:** Technicians can photograph analog pressure dials or corroded nameplates; local AI reads the dial and verifies it against the manual.
* **Non-Bypassable Safety Gates:** If the AI determines that an emergency valve must be opened, it automatically pauses execution, creates an approval request, and notifies the Shift Superintendent.

---

## 2. How It Works (The 6 Core Stations)

```
+-------------------------------------------------------------------------------+
|  1. THE FRONT DESK (FastAPI / main.py & api/)                                 |
|     Receives requests from operator screens or terminals, verifies workspaces,|
|     and routes to the appropriate agent.                                     |
+---------------------------------------+---------------------------------------+
                                        |
        +-------------------------------+-------------------------------+
        |                                                               |
+-------v-------------------------------+       +-----------------------v-------+
|  2. THE FILING CABINET                |       |  3. THE MANUALS LIBRARY       |
|     (SQLite / database.py, models.py) |       |     (Vector RAG / retriever)  |
|     Stores workspaces, agents, runs,  |       |     Indexes PDFs and returns  |
|     and full event audit timelines.   |       |     exact page citations.     |
+---------------------------------------+       +-------------------------------+
        |                                                               |
        +-------------------------------+-------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|  4. THE PHYSICAL PLANT GRAPH (core/graph_memory.py)                           |
|     Tracks P&ID physical connections: which pump feeds which reactor, what    |
|     sensor monitors it, and which safety relief valve protects it.            |
+---------------------------------------+---------------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|  5. THE LOCAL BRAIN (core/providers.py & ollama_provider.py)                 |
|     Runs Llama 3.2 3B (Reasoning) and Moondream 1B (Vision/OCR) locally on    |
|     the workstation GPU with zero outbound internet traffic.                  |
+---------------------------------------+---------------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|  6. THE TOOLBOX & SAFETY GATE (core/tools.py & approvals.py)                  |
|     Safe sensor checks run immediately. High-risk actions (valve actuation)   |
|     pause the system until a human supervisor clicks [APPROVE].               |
+-------------------------------------------------------------------------------+
```

---

## 3. File-by-File Technical Guide

### A. Web Server & Configuration
1. **`src/cognishift/app/main.py`:** Central FastAPI application. Configures the startup lifespan, mounts API routers, verifies local database initialization, and hosts the operator console.
2. **`src/cognishift/app/config.py`:** Singleton settings module powered by Pydantic v2. Resolves absolute directory paths and enforces sovereign mode.
3. **`src/cognishift/app/static/index.html`:** Clean, interactive operator dashboard for document uploads, agent runs, and approval management.

### B. Database & Schemas
4. **`src/cognishift/app/db/database.py`:** Manages local SQLite connection pools using `aiosqlite`. Enforces Write-Ahead Logging (WAL) and foreign keys.
5. **`src/cognishift/app/db/models.py`:** Pydantic models validating all request/response payloads (workspaces, agents, runs, approvals, multimodal image paths).

### C. Knowledge & Graph Memory Substrate
6. **`src/cognishift/core/retriever.py`:** Ingests technical PDFs with `pypdf`, computes dense semantic embeddings using FastEmbed (`bge-small-en-v1.5`), and queries ChromaDB with page-number citations.
7. **`src/cognishift/core/graph_memory.py`:** Persistent topological knowledge graph storing nodes (equipment, sensors, valves) and edges (`FEEDS_INTO`, `HAS_SENSOR`, `PROTECTED_BY`).

### D. AI Model Providers & Execution Engine
8. **`src/cognishift/core/providers.py`:** Abstract base class and factory pattern for model providers.
9. **`src/cognishift/core/ollama_provider.py`:** Connects to local Ollama via `httpx.AsyncClient`. Handles text generation and base64 multimodal vision analysis.
10. **`src/cognishift/core/engine.py`:** The central autonomous reasoning loop. Fuses visual telemetry, vector RAG, and graph topology; detects tool calling; and manages the Four-Eyes HITL pause/resume lifecycle.
11. **`src/cognishift/core/tools.py`:** Deterministic industrial tool registry connected to Tennessee Eastman SCADA telemetry and SAP PM maintenance records.

### E. Datasets & Test Scenarios
12. **`data/refinery_topology_iso15926.json`:** P&ID equipment specifications and physical safety relief connections.
13. **`data/telemetry_stream_tep.json`:** Dynamic time-series SCADA sensor stream with nominal baseline and overpressure surge fault injection.
14. **`data/maintenance_orders_sap_pm.json`:** SAP S/4HANA PM maintenance orders with ISO 14224 FMEA damage coding.
15. **`data/vision_test/`:** High-resolution test benchmark images of circular Bourdon pressure gauges and stamped metallic rating plates.

---

## 4. Real-World Operational Scenarios

### Scenario 1: Routine Sensor Telemetry Check
* **Operator Query:** *"Check pressure on sensor PT-101."*
* **Workflow:** Agent chooses tool `check_pressure(sensor_id="PT-101")` $\rightarrow$ System checks risk level (`read_only`) $\rightarrow$ Executes immediately $\rightarrow$ Reports nominal `105.5 PSI [GOOD]`.

### Scenario 2: Emergency Overpressure Surge with Four-Eyes Authorization
* **Alarm Trigger:** SCADA reports reactor pressure spiking to 495 PSI.
* **Workflow:** Agent checks `MRPL_HAZOP_OISD_SOP.pdf` and determines pressure exceeds MAWP 450 PSI limit $\rightarrow$ Proposes `emergency_pressure_relief` $\rightarrow$ System detects `service_interrupting` risk $\rightarrow$ Engine enters `paused` state $\rightarrow$ Shift Superintendent EMP-8921 clicks [APPROVE] $\rightarrow$ Engine resumes, vents 35 PSI to flare header, and restores safe conditions.

### Scenario 3: Multimodal Analog Gauge Inspection
* **Field Action:** Operator takes photo of a field pressure dial (`gauge_pressure_critical_485psi.png`).
* **Workflow:** Local Moondream VLM inspects image $\rightarrow$ Identifies dial `PT-101` pointing to 485 PSI in red warning zone $\rightarrow$ Engine matches against OISD-106 emergency manual $\rightarrow$ Alerts board operator and initiates safety venting protocol.

---

## 5. Presentation Pitch & FAQ Cheat Sheet

| Question / Topic | Hackathon Pitch Answer |
|:---|:---|
| **Why can't refineries use cloud AI?** | *"Refinery schematics and live sensor feeds are critical infrastructure secrets. CogniShift runs 100% on-premise on local GPUs with zero cloud egress."* |
| **How does CogniShift prevent AI hallucinations?** | *"Every recommendation is grounded in verified engineering manuals with exact page citations (`[Manual.pdf | Page X]`), and cross-checked against the plant topology graph."* |
| **Can the AI accidentally trip an emergency valve?** | *"No. Under our Four-Eyes Principle (OISD-STD-106 / IEC 62443), hazardous tools are physically intercepted by our state machine and require supervisor sign-off."* |
| **How does it read analog dials?** | *"We run an offline multimodal Vision-Language Model (Moondream) on the local GPU that reads the needle position and gauge text directly from photos."* |
