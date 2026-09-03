# CogniShift: Industrial Systems Architecture Specification

> **Technical Architecture Document for High-Consequence Petrochemical AI Deployment**  
> **Standard Compliance:** ISA-95 | ISO 15926-14 | OISD-STD-105/106 | IEC 62443 | Purdue PERA  

---

## 1. Industrial Zone Architecture (Purdue PERA Level 3.5 IDMZ)

CogniShift is designed to sit at **Purdue Model Level 3.5 (Industrial Demilitarized Zone - IDMZ)**, serving as an intelligent advisory layer between Level 3 (Manufacturing Operations & Plant Historians) and Level 4 (Enterprise IT):

```
+-----------------------------------------------------------------------+
|  LEVEL 4: ENTERPRISE IT NETWORK (ERP, SAP S/4HANA PM, Email)          |
+-----------------------------------------------------------------------+
                                   ▲
                          Firewall / Air-Gap
                                   ▼
+-----------------------------------------------------------------------+
|  LEVEL 3.5: COGNISHIFT SOVEREIGN WORKBENCH (IDMZ)                     |
|  • Local NVIDIA GPU Inference (Llama 3.2 3B + Moondream 1B)          |
|  • Local FastEmbed + ChromaDB Vector Store                            |
|  • Plant Topology Knowledge Graph (ISO 15926 / SQLite WAL)            |
|  • Four-Eyes Dual Authorization Safety Interlock                      |
+-----------------------------------------------------------------------+
                                   ▲
                          Firewall / Data Diode
                                   ▼
+-----------------------------------------------------------------------+
|  LEVEL 3: PLANT OPERATIONS & SCADA (DCS, Plant Historian, Alarms)     |
+-----------------------------------------------------------------------+
                                   ▲
                                   ▼
+-----------------------------------------------------------------------+
|  LEVEL 1 & 2: CONTROLLERS & SENSORS (PLCs, Bourdon Dials, Valves)     |
+-----------------------------------------------------------------------+
```

---

## 2. Knowledge Substrate: Hybrid GraphRAG

Traditional Vector RAG retrieves isolated paragraphs but fails to grasp physical mechanical connections. CogniShift implements **Hybrid GraphRAG**:

### 2.1. Vector Layer (Unstructured Knowledge)
* Extracts text from operating procedures (`OISD-STD-106`, `API 610`, `HAZOP Study`).
* FastEmbed (`BAAI/bge-small-en-v1.5`) generates 384-dimensional dense vectors on CPU.
* ChromaDB performs cosine similarity search filtered by `workspace_id`.

### 2.2. Graph Layer (Physical Plant Topology - ISO 15926 / ISA-95)
* Stored in SQLite relational tables:
  * `graph_nodes (id, workspace_id, name, entity_type, properties)`
  * `graph_edges (id, workspace_id, source_node_id, relation_type, target_node_id, properties)`
* Models physical relations:
  * `Pump-101A` $\xrightarrow{\text{FEEDS\_INTO}}$ `Reactor-B`
  * `Reactor-B` $\xrightarrow{\text{PROTECTED\_BY}}$ `SV-402`
  * `SV-402` $\xrightarrow{\text{DISCHARGES\_TO}}$ `Flare-Header`
  * `Pump-101A` $\xrightarrow{\text{HAS\_SENSOR}}$ `PT-101` (Discharge Pressure)
  * `Pump-101A` $\xrightarrow{\text{HAS\_SENSOR}}$ `TT-204` (Bearing Metal Temperature)
* Multi-hop traversal expands query entities to inject structural plant connections directly into the LLM prompt.

---

## 3. Four-Eyes Dual Authorization Interlock (HITL)

In compliance with **OISD-STD-106** and **IEC 62443**, autonomous execution of physical or service-interrupting actions is strictly prohibited.

### State Machine Lifecycle:
```
[RUN_STARTED]
      │
[RETRIEVAL] ──► (Vector RAG + Graph Topology + Visual Telemetry)
      │
[MODEL_REASONING]
      │
      ▼
Is Action High Risk?
 ├── NO  ──► [EXECUTE_TOOL] ──► [COMPLETE]
 └── YES ──► [TRANSITION TO PAUSED]
                  │
                  ▼
         Queue in approval_requests
                  │
         Supervisor Review (Web / CLI / API)
         ├── REJECT ──► [CANCELLED]
         └── APPROVE ─► [RESUME_RUN] ──► [EXECUTE_TOOL] ──► [COMPLETE]
```

---

## 4. Multimodal Computer Vision & Industrial OCR Pipeline

Field technicians can inspect equipment visually without manual typing:
1. **Image Input:** Analog Bourdon gauge photos or metallic rating plates uploaded via `/api/v1/runs` or `python cli.py run execute --image`.
2. **Local Vision Inference:** `moondream:latest` (1.86B parameter VLM) analyzes image on local GPU.
3. **Telemetry Extraction:** Identifies pointer needle angle, dial units (PSI), operating status, and stamped equipment tags (`PT-101`, `P-101A`).
4. **Knowledge Fusing:** Injects visual findings into the LLM prompt alongside RAG manuals and plant topology graph.

---

## 5. Terminal CLI Workbench

CogniShift provides a standalone terminal interface (`cli.py`) built with Typer + Rich for headless edge server deployments and SSH-based operator sessions:
- **8 Command Groups:** `workspace`, `agent`, `knowledge`, `graph`, `telemetry`, `run`, `approvals`, and `chat`.
- **Interactive REPL:** Persistent operator chat session with `/image`, `/status`, `/approvals`, `/telemetry`, `/approve`, and `/clear` slash commands.
- **Full Feature Parity:** Every REST API endpoint has a corresponding CLI command with identical data access.
- **Supervisor Review:** Four-Eyes approval can be performed via the web console (`/static/index.html`), Swagger API (`/docs`), or the terminal CLI (`python cli.py approvals approve <id>`).

See **[CLI.md](CLI.md)** for the complete command reference.
