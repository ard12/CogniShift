# CogniShift: System Benchmark & Verification Report

Technical benchmark results and empirical validation of the local on-premise workbench.

**Test Environment:**
* Operating System: Windows 11
* Python Runtime: Python 3.12
* Local GPU: NVIDIA GeForce RTX 3050 Laptop GPU (6.0 GB VRAM)
* Local Model Host: Ollama (hosting `llama3.2:3b` and `moondream:latest`)
* Local Embeddings: FastEmbed (`BAAI/bge-small-en-v1.5` on CPU)
* Vector Database: ChromaDB (local persistence)
* Relational Database: SQLite with Write-Ahead Logging (`aiosqlite` WAL mode)

---

## 1. Summary Benchmark Matrix

| Benchmark Area | Focus | Workload / Dataset | Result | Key Metric |
|:---|:---|:---|:---:|:---:|
| **Database Integrity** | CRUD & Foreign Keys | 10 SQLite Tables (WAL Mode) | Pass | < 0.25 s test suite execution |
| **Document Retrieval** | Large Document Search | 500-page manual (787 vector chunks) | Pass | 1.48 s query retrieval time |
| **Industrial Workflow** | Topology + Telemetry + HITL | Simulated TEP overpressure + SAP PM | Pass | 5/5 test scenarios passing |
| **Multimodal Vision** | Analog Dials & Rating Plates | Test gauge photos & equipment plates | Pass | 0.93 s – 6.57 s VLM inference |

---

## 2. Benchmark Suite 1: Database Operations

Automated async database testing with `pytest -v`:
* **Tables Verified:** `workspaces`, `agent_definitions`, `knowledge_sources`, `tool_definitions`, `agent_runs`, `run_events`, `approval_requests`, `audit_events`, `graph_nodes`, `graph_edges`.
* **Foreign Key Constraints:** Verified cascading rules; child records are cleaned up when workspaces or agents are deleted.
* **Concurrency:** Write-Ahead Logging (WAL) ensures reads and writes do not lock each other during standard operations.

---

## 3. Benchmark Suite 2: Document Ingestion & Retrieval Stress Test

To evaluate vector retrieval performance over larger manuals, a 500-page synthetic technical manual was indexed:
* **Corpus Size:** 1.05 MB PDF containing 787 section chunks.
* **Ingestion:** Text extracted page-by-page, chunked into 800-character segments with 150-character overlaps, and embedded into local ChromaDB via FastEmbed.
* **Retrieval Latency:** 1.48 seconds to perform cosine similarity search over 787 chunks and format citations.
* **Citation Precision:** Correctly retrieved specific pressure and temperature thresholds with exact page numbers.

---

## 4. Benchmark Suite 3: Simulated Industrial Workflow Benchmark

Validated using `scratch/test_industrial_data_workflow.py` with synthetic industrial datasets:
* **Simulated Datasets:**
  * SCADA telemetry stream modeled on the Tennessee Eastman Process (TEP).
  * Maintenance work orders modeled on SAP S/4HANA PM and ISO 14224 failure codes.
  * Plant equipment topology modeled on ISO 15926 relationships.
* **Workflow Test Sequence:**
  1. **Vector Search:** Retrieved safety limits from synthetic operating manual (`MRPL_HAZOP_OISD_SOP.pdf`) in 1.12 s.
  2. **Equipment Topology Traversal:** 2-hop traversal (`Pump-101A` $\to$ `PT-101` $\to$ `Reactor-B` $\to$ `SV-402`) in 12 ms.
  3. **Sensor Telemetry:** Read nominal sensor value (105.5 PSI) and overpressure condition (495.2 PSI).
  4. **Safety Interlock:** The reasoning loop proposed an emergency relief action. The state machine intercepted the call, verified that the tool required approval, and transitioned the run to `paused`.
  5. **Supervisor Approval:** The simulated supervisor approved the request, allowing the engine to resume and complete the action.

---

## 5. Benchmark Suite 4: Vision & Gauge Reading Benchmark

Evaluated using `scratch/test_multimodal_vision_pipeline.py` with local `moondream:latest` (1.86B parameter VLM) on the NVIDIA RTX 3050 GPU.

**Test Scenarios:**

| Scenario | Input Image | Model Prompt | Latency | Observed Result |
|:---|:---|:---|:---:|:---|
| **Nominal Gauge** | `gauge_pressure_nominal_105psi.png` | Read pressure dial | 1.39 s | Identified dial pointing to approximately 105 PSI. |
| **Critical Gauge** | `gauge_pressure_critical_485psi.png` | Check if pointer is in red zone | 0.93 s | Detected needle in upper red danger zone (>450 PSI). Triggered safety approval path. |
| **Equipment Nameplate** | `nameplate_pump_p101a.png` | Read rating plate text | 6.57 s | Extracted pump tag (`P-101A`) and manufacturer details. |

---


---

## 6. Benchmark Suite 5: Network Sovereignty & Policy Enforcement

Evaluated via the Phase 6 test suite (`tests/test_phase6_*.py`):

| Test Category | Target / Condition | Result | Latency / Metric |
|:---|:---|:---:|:---:|
| **Policy Evaluation** | 19 IP classification & rebinding tests | Pass | < 0.2 ms per decision |
| **Local Inference Egress** | Real Ollama query via sovereign transport | Pass | 200 OK, event logged as ALLOWED |
| **Public Egress Interception** | Outbound request to 93.184.216.34:80 | Pass | Blocked prior to socket connection |
| **LAN Egress Interception** | Outbound request to 192.168.1.1:8080 | Pass | Blocked prior to socket connection |
| **FastEmbed Offline Mode** | Model loading with missing cache | Pass | Fails closed without downloading |
| **Model Availability** | Requesting non-existent Ollama model | Pass | Fails closed without auto-pull |
| **Sensitive Data Redaction** | Audit ledger inspection with injected tokens | Pass | 0 sensitive markers logged |
| **Observer Negative Control** | Synthetic socket connection on port 19876 | Pass | Socket detected and logged |
| **Observer Workflow Check** | Active Ollama inference & embedding generation | Pass | 0 unauthorized connections |
| **Frontend Static Scan** | Inspection of index.html & static CSS | Pass | 0 external CDN links |

Total Repository Automated Tests: **196 passed**, 0 failed, 0 skipped.

---

## 7. System Evaluation Metrics

Measured via static analysis and test suite execution:

| Metric | Score | Description |
|:---|:---:|:---|
| **Tool Call Detection (TCA)** | 100.0% | Correct parsing of structured tool calls across test queries |
| **Parameter Extraction (PEA)** | 80.0% | Correct extraction of tool parameter keys and values from model text |
| **Approval Interception (SIR)** | 100.0% | All high-risk tools in the test suite were paused for supervisor approval |
| **False Alarm Rate (FAR)** | 0.0% | Safe, read-only tools were executed without unnecessary approval pauses |
| **Citation Precision (SLCP)** | 100.0% | Page-level citations verified against indexed document chunks |
| **Average Vector Retrieval Time** | 146.2 ms | Average ChromaDB cosine similarity search time |

---

## 8. Operational Limitations

* **Simulated Plant Environment:** SCADA telemetry streams and SAP PM maintenance orders are synthetic test datasets, not live plant systems.
* **Handwriting:** Handwritten notes are parsed on a best-effort basis. Where OCR confidence is low, uncertainty is preserved.
* **Model Size:** Local inference uses compact open-weight models (3B parameter LLM, 1.86B parameter VLM) to run on consumer-grade hardware. Complex reasoning can require prompt guidance.
* **Network Boundaries:** Phase 6 network policy and sovereignty enforcement is complete and verified with 196 tests passing.
