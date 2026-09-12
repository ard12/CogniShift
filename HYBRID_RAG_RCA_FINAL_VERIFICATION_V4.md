# CogniShift Sovereign AI Workbench — Final Hybrid Multimodal RCA Truth-Chain Verification Report (Benchmark V4)

**Audit Execution Date:** 2026-09-12 12:44:57 UTC  
**Audit Standard:** Final Execution & Evidence Truth Repair (Zero Manufactured Claims, Real Provenance, Dual Scoring)  
**Target Hardware:** NVIDIA GeForce RTX 3050 Laptop GPU (6GB VRAM, CUDA 12.0)  
**Inference Engine:** Local Ollama Moondream 1.8B VLM | DeepSeek R1 7B / Qwen 2.5 7B | ChromaDB  
**Multimodal Late-Interaction Model:** Qdrant/colmodernvbert ONNX on CUDA (device: cuda)  
**Sandbox Runtime:** Real Isolated Docker Container (`cognishift/sandbox-python:3.12-v1`) with SHA-256 Execution Provenance  
**Sovereignty & Egress Statement:**  
> **Local sovereign execution with no public-cloud model dependency during the verified run.**  
> **Zero observed external egress during benchmark execution.**

---

## 1. Executive Summary & Dual-Scoring Verdict

Benchmark V4 enforces strict **Dual Scoring**: a scenario is only graded as a **PASS** if BOTH the outcome matches ground truth (`outcome_match`) AND the supporting evidence chain is independently validated without circularity or fabricated citations (`evidence_chain_valid`).

| Metric | Target Threshold | Measured Score | Evaluation Status |
| :--- | :---: | :---: | :---: |
| **Dual-Scoring Scenario Pass Rate** | >= 95.0% | **100.0%** (7/7) | **PASS** |
| **Root Cause Status Accuracy (RCSA)** | >= 95.0% | **100.0%** | **PASS** |
| **Primary Cause Accuracy (Unioned)** | >= 95.0% | **100.0%** | **PASS** |
| — *Physical Failure PCA (RCA 1, 2, 5, 6)* | >= 95.0% | **100.0%** (4/4) | **PASS** |
| — *Safety/Terminal State Accuracy (RCA 3, 4, 7)* | 100.0% | **100.0%** (3/3) | **PASS** |
| **Claim Support Precision (CSP)** | >= 90.0% | **100.0%** | **PASS** |
| **Source Coverage (SC)** | >= 85.0% | **100.0%** | **PASS** |
| **Citation Accuracy (CA)** | >= 95.0% | **86.8%** (4/7 scored; OOD excluded) | **DEGRADED** |
| **False Cause Rate (FCR)** | == 0.0% | **0.0%** | **PASS** |
| **Section 17 Structure Compliance** | 100.0% | **100.0%** | **PASS** |
| **Destructive Finalizer Regression Free** | Zero Regression | **Zero Regressions** | **PASS** |
| **Final-Step Protocol Lockout** | Zero Rogue Calls | **Zero Rogue Calls** | **PASS** |
| **Real Docker Sandbox Nonce Verification** | SHA-256 Provenance | **Verified (Non-Simulated)** | **PASS** |
| **RCA-06 3-Condition Ablation Study** | Dynamic Visual Binding | **VERIFIED** | **PASS** |

---

## 2. 5-Point Strict Preflight Verifications

Prior to benchmark execution, all 5 system truth invariants were asserted in fail-closed mode:

1. **Authoritative Fixture SHA-256 Checksums**: All 15 source documents verified on disk against authoritative manifest checksums.
2. **Dynamic SQLite Source Resolution**: All document IDs dynamically resolved via `knowledge_sources` table. Zero hardcoded database IDs.
3. **Multi-Vector On-Disk Patches & Live VLM Inspection**: Verified `.npy` multi-vector cache files on disk for P&ID source 1075; live MaxSim visual query executed (score 15.689); live VLM inspection confirmed tags corroborated.
4. **Authoritative Sensor Resolution**: Verified equipment-to-sensor mappings (`P-101A` -> `PT-101`, `K-101` -> `TT-204`).
5. **Real Docker Sandbox Nonce Verification**: Executed live nonce `COGNISHIFT_NONCE_1789216041_585b9cde` in container image `cognishift/sandbox-python:3.12-v1`. Verified `simulated = False`, exit code 0, and SHA-256 execution provenance. Deliberate syntax failure test confirmed exit code != 0, zero fake artifacts, and real stderr capture.

---

## 3. Scenario Breakdown & Dual-Scoring Audit Table

| Scenario ID | Name | RCA Status | Cause Code | Outcome | Evidence Chain | Scenario Pass | CA | Latency |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `RCA-01` | P-101A Suction Starvation & Cavitation Trip (Non-Leaking Query) | `PLAUSIBLE_HYPOTHESIS` | `SUCTION_STARVATION_CAVITATION` | MATCH | VALID | **PASS** | 79.4% | 187428.6ms |
| `RCA-02` | K-101 Centrifugal Compressor Overheat & ESD Trip | `PLAUSIBLE_HYPOTHESIS` | `BEARING_OVERHEAT` | MATCH | VALID | **PASS** | 90.3% | 106766.4ms |
| `RCA-03` | P-101A Missing Evidence Honest Abstention Gate | `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE` | MATCH | VALID | **PASS** | N/A | 72023.9ms |
| `RCA-04` | Out-of-Distribution (OOD) Nonexistent Asset Safety Gate | `ASSET_NOT_FOUND` | `ASSET_NOT_FOUND` | MATCH | VALID | **PASS** | N/A | 474.1ms |
| `RCA-05` | Final-Step Protocol Tool Lockout & Safe Interception | `PLAUSIBLE_HYPOTHESIS` | `BEARING_OVERHEAT` | MATCH | VALID | **PASS** | 87.7% | 75786.6ms |
| `RCA-06` | Visual-Dependent P&ID RCA (Hydrocracker R-301 / FV-302) | `CONFIRMED_CAUSE` | `VALVE_STEM_BINDING` | MATCH | VALID | **PASS** | 89.7% | 201622.4ms |
| `RCA-07` | Inconclusive Investigation & Missing Telemetry (BFP-02) | `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE` | MATCH | VALID | **PASS** | N/A | 51781.7ms |

---

## 4. RCA-06 True 3-Condition Ablation Study

Scenario: **Hydrocracker Reactor R-301 / Control Valve FV-302 P&ID Spatial Dependency**

| Condition | Executed Channels | Spatial Link Supported? | Visual E-ID Bound? | Outcome Status |
| :--- | :---: | :---: | :---: | :---: |
| **Condition A (Text-Only)** | ['text'] | **False** | No | `INSUFFICIENT_EVIDENCE` |
| **Condition B (Text + Topology)** | ['text', 'topology'] | **False** (No Leak) | No | `PLAUSIBLE_HYPOTHESIS` |
| **Condition C (Full Multimodal)** | ['text', 'visual', 'topology'] | **True** | **Yes [E7]** | `CONFIRMED_CAUSE` |

**Ablation Verdict**: **VERIFIED**  
- **Condition A (Text-Only)**: Visual channel disabled. Spatial link is `UNSUPPORTED`. Primary cause cannot reference visual schematic.
- **Condition B (Text + Topology)**: Plant topology present without spatial coordinates. Strict spatial leak prevention prevents hallucination of upstream flow.
- **Condition C (Full Multimodal)**: Visual late-interaction multi-vector retriever locates the P&ID blueprint. Local Moondream VLM extracts and deterministic verifier confirms `FV-302 UPSTREAM_OF R-301`. Visual evidence item is bound directly into `primary_cause_supporting_evidence_ids`.

---

## 5. Production 6-Archetype Document Retrieval Matrix

| Document Archetype | Reference Filename | Format-Aware Locator Output | Measured Latency | Retrieval Status | Matrix Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Narrative PDF** | `Pump_Maintenance_SOP.pdf` | `[Pump_Maintenance_SOP.pdf | Page 1]` | 134.2ms | `SUCCESS` | **PASS** |
| **Scanned PDF** | `SCAN-LOG-REACTOR-R301_Bed_Differential_Pressure_CleanScan.pdf` | `[SCAN-LOG-REACTOR-R301_Bed_Differential_Pressure_CleanScan.pdf | Page 1]` | 7072.8ms | `SUCCESS` | **PASS** |
| **P&ID Blueprint** | `RCA-CASE-A-DOC2_Feed_Control_FV302_Spatial_PID.pdf` | `[RCA-CASE-A-DOC2_Feed_Control_FV302_Spatial_PID.pdf | Page 1]` | 13.8ms | `SUCCESS` | **PASS** |
| **Dense Engineering Table** | `ENG-TBL-HEX-301A_Reactor_Effluent_Exchanger_Grid_2024.pdf` | `[ENG-TBL-HEX-301A_Reactor_Effluent_Exchanger_Grid_2024.pdf | Page 1]` | 4138.1ms | `SUCCESS` | **PASS** |
| **Spreadsheet (XLSX)** | `MRPL_Unit01_SCADA_Continuous_Telemetry_48H_REV_B.xlsx` | `[MRPL_Unit01_SCADA_Continuous_Telemetry_48H_REV_B.xlsx | Sheet SCADA_48H | Rows 1-100 | Cols A-H]` | 112.0ms | `SUCCESS` | **PASS** |
| **Document (DOCX)** | `Report_MRPL_Financial_History_3Y_REV_B.docx` | `[Report_MRPL_Financial_History_3Y_REV_B.docx | Section Operational Summary | Page 1]` | 109.5ms | `SUCCESS` | **PASS** |

---

## 6. Truth-Chain Invariants & Historical Immutability Guarantees

1. **Historical Verification Immutability**: Historical verification outputs in `data/rca_final_verification/` (V1), `data/rca_final_verification_v2/` (V2), and `data/rca_final_verification_v3/` (V3) remain 100% untouched and byte-preserved.
2. **Zero Cloud Ingress / Egress**: Zero external API calls. All embeddings and LLM reasoning run exclusively on localhost via Ollama, FastEmbed ONNX, and ColModernVBERT.
3. **Real Docker Sandbox Execution**: All tool executions use real container sandboxing with SHA-256 provenance tracking. Zero fallbacks to simulated execution in production.
4. **Honest Multi-Modal Accounting**: Word documents (`.docx`) are honestly documented as `DOCX TEXT RAG = ACTIVE`, `DOCX VISUAL RAG = NOT IMPLEMENTED / DEGRADED`.
5. **Zero Synthetic Timings**: All latencies represent actual clock intervals measured at code execution boundaries using `time.perf_counter()`.
