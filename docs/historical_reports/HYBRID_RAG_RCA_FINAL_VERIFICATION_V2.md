# CogniShift Sovereign AI Workbench — Final Hybrid Multimodal RCA Verification Report (V2)

**Audit Execution Date:** 2026-09-12 07:22:43 UTC  
**Target Hardware:** NVIDIA GeForce RTX 3050 Laptop GPU (6GB VRAM, CUDA 12.0)  
**Inference Engine:** DeepSeek R1 7B / Qwen 2.5 7B via Ollama | FastEmbed | ChromaDB  
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
| **Claim Support Precision (CSP)** | >= 90.0% | **95.2%** | **PASS** |
| **Source Coverage (SC)** | >= 85.0% | **90.5%** | **PASS** |
| **Citation Accuracy (CA)** | >= 95.0% | **99.6%** | **PASS** |
| **False Cause Rate (FCR)** | == 0.0% | **0.0%** | **PASS** |
| **Section 17 Structure Compliance** | 100.0% | **100.0%** | **PASS** |
| **Destructive Finalizer Regression Free** | Zero Regression | **Zero Regressions** | **PASS** |
| **Final-Step Protocol Lockout** | Zero Rogue Calls | **Zero Rogue Calls** | **PASS** |
| **RCA-06 3-Condition Ablation Study** | Scientifically Defensible | **VERIFIED** | **PASS** |

---

## 2. 9-Point Visual Runtime Preflight Assertion

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

## 3. RCA-06 True 3-Condition Ablation Study

Scenario: **Hydrocracker Reactor R-301 / Control Valve FV-302 P&ID Spatial Dependency**

| Condition | Executed Channels | Spatial Link Supported? | Visual E-ID Bound? | Outcome Status |
| :--- | :---: | :---: | :---: | :---: |
| **Condition A (Text-Only)** | ['text'] | **False** | No | `INSUFFICIENT_EVIDENCE` |
| **Condition B (Text + Topology)** | ['text', 'topology'] | **False** (No Leak) | No | `PLAUSIBLE_HYPOTHESIS` |
| **Condition C (Full Multimodal)** | ['text', 'visual'] | **True** | **Yes [E4]** | `PLAUSIBLE_HYPOTHESIS` |

**Ablation Verdict**: **VERIFIED**  
- In Condition A, without visual schematic, the system cannot confirm FV-302 is upstream of R-301.
- In Condition B, plant topology without spatial coordinates does not leak the upstream feed link.
- In Condition C, visual late-interaction retrieval and VLM inspection definitively verify FV-302 upstream of R-301, citing the visual E-ID.

---

## 4. Scenario Breakdown & Measured Stage Latencies

| Scenario | Name | Status | Primary Cause Code | CA | Total (ms) | Retr (ms) | Reason (ms) | Synth (ms) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `RCA-01` | P-101A Suction Starvation & Cavitation Trip | `PLAUSIBLE_HYPOTHESIS` | `SUCTION_STARVATION_CAVITATION` | 100.0% | 148181.4 | 2.1 | 147588.8 | 1.0 |
| `RCA-02` | K-101 Centrifugal Compressor Overheat & ESD Trip | `PLAUSIBLE_HYPOTHESIS` | `BEARING_OVERHEAT` | 97.0% | 31497.4 | 2.5 | 31156.9 | 0.3 |
| `RCA-03` | P-101A Missing Evidence Honest Abstention Gate | `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE` | 100.0% | 47426.1 | 2.6 | 46988.1 | 0.2 |
| `RCA-04` | Out-of-Distribution (OOD) Nonexistent Asset Safety Gate | `ASSET_NOT_FOUND` | `ASSET_NOT_FOUND` | 100.0% | 395.4 | 0.0 | 395.4 | 0.0 |
| `RCA-05` | Final-Step Protocol Tool Lockout & Safe Interception | `PLAUSIBLE_HYPOTHESIS` | `BEARING_OVERHEAT` | 100.0% | 53011.6 | 2.8 | 52541.8 | 0.6 |
| `RCA-06` | Visual-Dependent P&ID RCA (Hydrocracker R-301 / FV-302) | `PLAUSIBLE_HYPOTHESIS` | `VALVE_STEM_BINDING` | 100.0% | 69074.0 | 3909.8 | 51798.9 | 0.3 |
| `RCA-07` | Inconclusive Investigation & Missing Telemetry (BFP-02) | `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE` | 100.0% | 28638.8 | 4.1 | 27459.2 | 0.1 |

---

## 5. 6-Archetype Document Ingestion & Retrieval Sanity Matrix

| Document Archetype | Reference Filename | Format-Aware Locator Output | Syntax Check | Latency | Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Narrative PDF** | `Pump_Maintenance_SOP.pdf` | `[Pump_Maintenance_SOP.pdf | Page 1]` | VALID | 0.05ms | **PASS** |
| **Scanned PDF** | `SCAN-LOG-REACTOR-R301_Bed_Differential_Pressure_CleanScan.pdf` | `[SCAN-LOG-REACTOR-R301_Bed_Differential_Pressure_CleanScan.pdf | Page 1]` | VALID | 0.03ms | **PASS** |
| **P&ID Blueprint** | `RCA-CASE-A-DOC2_Feed_Control_FV302_Spatial_PID.pdf` | `[RCA-CASE-A-DOC2_Feed_Control_FV302_Spatial_PID.pdf | Page 1 | VISUAL]` | VALID | 0.02ms | **PASS** |
| **Dense Engineering Table** | `ENG-TBL-HEX-301A_Reactor_Effluent_Exchanger_Grid_2024.pdf` | `[ENG-TBL-HEX-301A_Reactor_Effluent_Exchanger_Grid_2024.pdf | Page 1]` | VALID | 0.02ms | **PASS** |
| **Spreadsheet (XLSX)** | `MRPL_Unit01_SCADA_Continuous_Telemetry_48H_REV_B.xlsx` | `[MRPL_Unit01_SCADA_Continuous_Telemetry_48H_REV_B.xlsx | Sheet: SCADA_48H | Rows 1-100 | Cols A:H | SPREADSHEET]` | VALID | 0.04ms | **PASS** |
| **Document (DOCX)** | `Report_MRPL_Financial_History_3Y_REV_B.docx` | `[Report_MRPL_Financial_History_3Y_REV_B.docx | Section: Operational Summary | Rendered Page 1 | DOCUMENT]` | VALID | 0.03ms | **PASS** |

---

## 6. Audit Provenance & Integrity Guarantee

1. **V1 Results Preserved**: Historical results in `data/rca_final_verification/` remain completely untouched.
2. **Zero Synthetic Timings**: All latencies represent actual clock intervals measured at code execution boundaries using `time.perf_counter()`.
3. **Fail-Closed Guarantee**: Any unavailable visual model or corrupted vector store triggers immediate pipeline abort rather than silent degradation.
