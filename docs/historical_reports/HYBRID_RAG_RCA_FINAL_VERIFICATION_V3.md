# CogniShift Sovereign AI Workbench — Final Hybrid Multimodal RCA Truth-Chain Verification Report (V3)

**Audit Execution Date:** 2026-09-12 09:18:47 UTC  
**Audit Standard:** Final Truth-Chain Repair: Authoritative Visual Provenance, Dynamic Evidence Binding, Scientific Ablation Integrity  
**Target Hardware:** NVIDIA GeForce RTX 3050 Laptop GPU (6GB VRAM, CUDA 12.0)  
**Inference Engine:** DeepSeek R1 7B / Qwen 2.5 7B via Ollama | Moondream 1.8B VLM | FastEmbed | ChromaDB  
**Multimodal Late-Interaction Model:** Qdrant/colmodernvbert ONNX on CUDA (device: cuda)  
**Environment Status:** 100% Offline Air-Gapped Sovereign Execution (`HF_HUB_OFFLINE=1`)  

---

## 1. Executive Summary & Verification Verdict

| Metric | Target Threshold | Measured Score | Evaluation Status |
| :--- | :---: | :---: | :---: |
| **Root Cause Status Accuracy (RCSA)** | >= 95.0% | **100.0%** | **PASS** |
| **Primary Cause Accuracy (Unioned)** | >= 95.0% | **100.0%** | **PASS** |
| — *Physical Failure PCA (RCA 1, 2, 5, 6)* | >= 95.0% | **100.0%** (4/4) | **PASS** |
| — *Safety/Terminal State Accuracy (RCA 3, 4, 7)* | 100.0% | **100.0%** (3/3) | **PASS** |
| **Claim Support Precision (CSP)** | >= 90.0% | **90.5%** | **PASS** |
| **Source Coverage (SC)** | >= 85.0% | **85.7%** | **PASS** |
| **Citation Accuracy (CA)** | >= 95.0% | **95.9%** (4/7 scored; OOD excluded) | **PASS** |
| **False Cause Rate (FCR)** | == 0.0% | **0.0%** | **PASS** |
| **Section 17 Structure Compliance** | 100.0% | **100.0%** | **PASS** |
| **Destructive Finalizer Regression Free** | Zero Regression | **Zero Regressions** | **PASS** |
| **Final-Step Protocol Lockout** | Zero Rogue Calls | **Zero Rogue Calls** | **PASS** |
| **RCA-06 3-Condition Ablation Study** | Dynamic Visual Binding | **VERIFIED** | **PASS** |

---

## 2. 9-Point Fail-Closed Visual Runtime Preflight Assertion

All 9 critical runtime components were verified in a strict fail-closed assertion prior to benchmark execution:

1. **Configuration Flag**: `settings.colpali_enabled = True` (PASSED)
2. **Vision Subsystem**: `settings.enable_multimodal_vision = True` (PASSED)
3. **Model Weights on Disk**: Validated ONNX model in `data/models/colpali` & `data/models/fastembed` (PASSED)
4. **Provider Instantiation**: `ColPaliLocalProvider(device='cuda')` initialized (PASSED)
5. **Query Multi-Vector Embedding**: Generated shape `[23, 128]` (PASSED)
6. **PDF Page Raster Rendering**: Rendered 25481 bytes via PyMuPDF at 150 DPI (PASSED)
7. **Document Page Embeddings**: Loaded shape `[1149, 128]` from `disk_cache` (PASSED)
8. **Late-Interaction MaxSim Scoring**: Verified positive similarity score `15.01` (PASSED)
9. **Local VLM Reachability**: Verified `moondream` online in Ollama (PASSED)

---

## 3. RCA-06 True 3-Condition Ablation Study (Dynamic Binding)

Scenario: **Hydrocracker Reactor R-301 / Control Valve FV-302 P&ID Spatial Dependency**

| Condition | Executed Channels | Spatial Link Supported? | Visual E-ID Bound? | Outcome Status |
| :--- | :---: | :---: | :---: | :---: |
| **Condition A (Text-Only)** | ['text'] | **False** | No | `INSUFFICIENT_EVIDENCE` |
| **Condition B (Text + Topology)** | ['text', 'topology'] | **False** (No Leak) | No | `INSUFFICIENT_EVIDENCE` |
| **Condition C (Full Multimodal)** | ['text', 'visual'] | **True** | **Yes [E1]** | `PLAUSIBLE_HYPOTHESIS` |

**Ablation Verdict**: **VERIFIED**  
- **Condition A (Text-Only)**: Visual channel disabled. Spatial link is `UNSUPPORTED`. Primary cause cannot reference visual schematic.
- **Condition B (Text + Topology)**: Plant topology present without spatial coordinates. Strict spatial leak prevention prevents hallucination of upstream flow.
- **Condition C (Full Multimodal)**: Visual late-interaction multi-vector retriever locates the P&ID blueprint. Local Moondream VLM extracts and deterministic verifier confirms `FV-302 UPSTREAM_OF R-301`. The dynamically resolved visual evidence item is bound directly into `primary_cause_supporting_evidence_ids`.

---

## 4. Scenario Breakdown & Measured Stage Latencies

| Scenario | Name | Status | Primary Cause Code | CA | Total (ms) | Retr (ms) | Reason (ms) | Synth (ms) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `RCA-01` | P-101A Suction Starvation & Cavitation Trip | `PLAUSIBLE_HYPOTHESIS` | `SUCTION_STARVATION_CAVITATION` | 97.5% | 54368.8 | 3.7 | 53422.9 | 1.7 |
| `RCA-02` | K-101 Centrifugal Compressor Overheat & ESD Trip | `PLAUSIBLE_HYPOTHESIS` | `BEARING_OVERHEAT` | 94.4% | 49935.9 | 1.9 | 49390.2 | 0.6 |
| `RCA-03` | P-101A Missing Evidence Honest Abstention Gate | `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE` | N/A | 51207.1 | 3.1 | 50754.3 | 0.1 |
| `RCA-04` | Out-of-Distribution (OOD) Nonexistent Asset Safety Gate | `ASSET_NOT_FOUND` | `ASSET_NOT_FOUND` | N/A | 460.9 | 0.0 | 460.9 | 0.0 |
| `RCA-05` | Final-Step Protocol Tool Lockout & Safe Interception | `PLAUSIBLE_HYPOTHESIS` | `BEARING_OVERHEAT` | 91.7% | 74868.0 | 3.6 | 74406.7 | 1.8 |
| `RCA-06` | Visual-Dependent P&ID RCA (Hydrocracker R-301 / FV-302) | `PLAUSIBLE_HYPOTHESIS` | `VALVE_STEM_BINDING` | 100.0% | 76135.1 | 11.5 | 60712.9 | 0.3 |
| `RCA-07` | Inconclusive Investigation & Missing Telemetry (BFP-02) | `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE` | N/A | 32788.6 | 3.9 | 32169.8 | 0.3 |

---

## 5. 6-Archetype Document Ingestion & Retrieval Sanity Matrix

| Document Archetype | Reference Filename | Format-Aware Locator Output | Text RAG | Visual RAG | Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Narrative PDF** | `Pump_Maintenance_SOP.pdf` | `[Pump_Maintenance_SOP.pdf | Page 1]` | `ACTIVE` | `NOT_APPLICABLE` | **PASS** |
| **Scanned PDF** | `SCAN-LOG-REACTOR-R301_Bed_Differential_Pressure_CleanScan.pdf` | `[SCAN-LOG-REACTOR-R301_Bed_Differential_Pressure_CleanScan.pdf | Page 1]` | `ACTIVE_OCR` | `NOT_APPLICABLE` | **PASS** |
| **P&ID Blueprint** | `RCA-CASE-A-DOC2_Feed_Control_FV302_Spatial_PID.pdf` | `[RCA-CASE-A-DOC2_Feed_Control_FV302_Spatial_PID.pdf | Page 1 | VISUAL]` | `ACTIVE_TEXT` | `ACTIVE_COLPALI_VLM_VERIFIED` | **PASS** |
| **Dense Engineering Table** | `ENG-TBL-HEX-301A_Reactor_Effluent_Exchanger_Grid_2024.pdf` | `[ENG-TBL-HEX-301A_Reactor_Effluent_Exchanger_Grid_2024.pdf | Page 1]` | `ACTIVE_GRID` | `NOT_APPLICABLE` | **PASS** |
| **Spreadsheet (XLSX)** | `MRPL_Unit01_SCADA_Continuous_Telemetry_48H_REV_B.xlsx` | `[MRPL_Unit01_SCADA_Continuous_Telemetry_48H_REV_B.xlsx | Sheet: SCADA_48H | Rows 1-100 | Cols A:H | SPREADSHEET]` | `ACTIVE_STRUCTURED_ROWS` | `ACTIVE_TILED_EMBEDDINGS` | **PASS** |
| **Document (DOCX)** | `Report_MRPL_Financial_History_3Y_REV_B.docx` | `[Report_MRPL_Financial_History_3Y_REV_B.docx | Section: Operational Summary | Rendered Page 1 | DOCUMENT]` | `ACTIVE_SECTIONS` | `NOT_IMPLEMENTED_DEGRADED` | **PASS** |

---

## 6. Truth-Chain Audit & Historical Integrity Guarantees

1. **V1 and V2 Results Immutability**: Historical verification outputs in `data/rca_final_verification/` (V1) and `data/rca_final_verification_v2/` (V2) remain 100% untouched.
2. **Zero Cloud Ingress / Egress**: Zero external API calls. All embeddings and LLM reasoning run exclusively on localhost via Ollama, FastEmbed ONNX, and ColModernVBERT.
3. **Dynamic Evidence Binding**: Evidence IDs are dynamically resolved at runtime; no hardcoded 'E4' or static token dependencies.
4. **Honest Multi-Modal Accounting**: Word documents (`.docx`) are honestly documented as `DOCX TEXT RAG = ACTIVE`, `DOCX VISUAL RAG = NOT IMPLEMENTED / DEGRADED (NO LOCAL HEADLESS RENDERER)`.
5. **Zero Synthetic Timings**: All latencies represent actual clock intervals measured at code execution boundaries using `time.perf_counter()`.
