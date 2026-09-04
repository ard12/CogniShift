# CogniShift Real-Data Benchmark Report

## 1. Benchmark Commit & Metadata
- **Git Commit:** 2bebe319b910e140d39e3ec45ee6e9962a1215b3
- **Parent Commit:** 0057463a570a8f752bbbd52a6330d03eafb9dd17
- **Branch:** main
- **Execution Date:** 2026-09-04
- **Operating Mode:** local (air-gapped / zero external network egress)

## 2. Hardware & Runtime Environment
- **Host OS:** Microsoft Windows 11 Home/Pro (Build 10.0.26200)
- **Python Version:** 3.12.10 (C:\\Users\\sitan\\AppData\\Local\\Programs\\Python\\Python312\\python.exe)
- **CPU:** AMD Ryzen 5 5600H (6 Cores, 12 Threads)
- **Host RAM:** 16.0 GB
- **GPU:** NVIDIA GeForce GTX 1650 Mobile (4.0 GB VRAM)
- **Container Engine:** Docker Desktop 29.7.2 (Linux container mode desktop-linux)
- **Local LLM Engine:** Ollama 0.33.3 (Listening on 127.0.0.1:11434)
  - Text Model: llama3.2:3b (Digest: a80c4f17fad5)
  - Vision Model: moondream:latest (Digest: 55fc3abd3867)
- **Local Embedding Engine:** FastEmbed 0.8.0 (BAAI/bge-small-en-v1.5, ONNX Runtime 1.26.0)
- **Local OCR Engine:** RapidOCR 1.4.4 (PaddleOCR PP-OCRv4 models, ONNX Runtime 1.26.0)

## 3. Dataset Provenance Manifest
As specified in enchmarks/datasets/manifest.json:
- **Real Industrial OCR Dataset:** NOT PROVISIONED (Status: PROVISIONING_REQUIRED)
- **Real Engineering PDF Dataset:** NOT PROVISIONED (Status: PROVISIONING_REQUIRED)
- **Real Technical RAG/QA Dataset:** NOT PROVISIONED (Status: PROVISIONING_REQUIRED)
- **Real Industrial Vision Dataset:** NOT PROVISIONED (Status: PROVISIONING_REQUIRED)
- **Local Synthetic Fixtures:** Present in repository (data/manuals/, data/vision_test/). Strictly reserved for unit/security testing and labeled as synthetic. In accordance with Section X1, X3, and X28 of the directive, synthetic fixtures are NOT substituted for real benchmark datasets.

## 4. Benchmark Metrics by Capability
- **Real Document OCR (CER, WER, Latency):** NOT BENCHMARKED (Awaiting real dataset provisioning)
- **Native PDF Extraction (Routing, Citation Accuracy):** NOT BENCHMARKED (Awaiting real dataset provisioning)
- **Knowledge Retrieval / RAG (Recall@k, MRR):** NOT BENCHMARKED (Awaiting real dataset provisioning)
- **Grounded Answer QA (Faithfulness, Citation Completeness):** NOT BENCHMARKED (Awaiting real dataset provisioning)
- **Industrial Vision (Gauge/Nameplate Accuracy, VRAM):** NOT BENCHMARKED (Awaiting real dataset provisioning)
- **Model Routing (Task Classification, Fallback Rate):** Unit test verified (100% on internal routing suite); NOT BENCHMARKED on external traces
- **Agent & Tool Execution (Completion, Approval Safety):** Unit test verified (100% on HITL state machine); NOT BENCHMARKED on external agent benchmark
- **Artifact Generation & Validation:** Unit test verified; NOT BENCHMARKED on external code generation suite
- **Docker Code Sandbox:** Security & resource limits verified (16/16 tests PASSED); performance under sustained concurrent execution NOT BENCHMARKED
- **Sovereignty & Egress Observation:** Verified empirically in Phase 6 Gate (32/32 tests PASSED; 0 unauthorized packets/events observed)
- **System Performance (Cold vs Warm Latency, VRAM):** NOT BENCHMARKED on external real datasets

## 5. Dataset Acquisition List for Human Operator Approval
In accordance with Section X2, internet downloads are blocked during strict runtime execution. The following datasets are submitted for operator approval and offline provisioning:
1. **OCR Benchmark:** Public scanned reports from NASA Technical Reports Server (NTRS) or OSHA Inspection Reports with ground-truth UTF-8 transcriptions.
2. **P&ID / Technical PDF:** Public Chemical Safety Board (CSB) incident investigation reports containing mixed native text, engineering schematics, and tabular data.
3. **Industrial Vision:** OpenGauge / Roboflow Industrial Pointer Meter dataset (circular analog dials and digital indicators under varied lighting and angles).
4. **RAG / QA Pairs:** Curated ground-truth Q&A pairs with verified page-level source references from CSB refinery incident reports.

## 6. Failure Analysis & Limitations
- **Zero Real Data Contamination:** No synthetic data was mislabeled or presented as real-world benchmark metrics.
- **Fail-Closed Sovereign Posture:** The platform refused to silently fetch external datasets from the internet, adhering strictly to zero-cloud egress policies.

## 7. Benchmark Manifest & Integrity
Artifact hashes recorded in enchmarks/benchmark_manifest.json.

## 8. Benchmark Verdict
REAL-DATA BENCHMARK GATE: BLOCKED — DATASET PROVISIONING REQUIRED
