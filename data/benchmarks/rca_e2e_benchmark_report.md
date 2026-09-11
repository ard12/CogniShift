# CogniShift Root Cause Analysis (RCA) End-to-End Reliability Benchmark Report

**Date:** 2026-09-11 17:43:48 UTC  
**Environment:** 100% Offline Air-Gapped Sovereign Hardware  
**GPU Accelerator:** NVIDIA GeForce RTX 3050 Laptop GPU (6GB VRAM, CUDA 12.0)  
**Inference Stack:** Local Ollama (`qwen2.5:7b`), FastEmbed, ChromaDB, ColPali MultiVector  

## Executive Summary

| Metric | Measured Score | Target Threshold | Compliance Status |
| :--- | :--- | :--- | :--- |
| **Root Cause Status Accuracy (RCSA)** | **100.0%** | ≥ 95.0% | ✅ PASSED |
| **Claim Support Precision (CSP)** | **100.0%** | ≥ 90.0% | ✅ PASSED |
| **Source Coverage (SC)** | **100.0%** | ≥ 85.0% | ✅ PASSED |
| **Citation Accuracy (CA)** | **87.1%** | ≥ 90.0% | ⚠ DEGRADED |
| **False Cause Rate (FCR)** | **0.0%** | ≤ 0.0% | ✅ PASSED |
| **Section 17 Structure Compliance** | **100%** | 100% | ✅ PASSED |
| **Destructive Finalizer Regression Free** | **100%** | 100% | ✅ PASSED |
| **Mean End-to-End Latency** | **48079.7 ms** | Informational | ℹ️ RECORDED |

## Scenario Breakdown

| ID | Scenario Name | Matched Status | Status Acc | CSP | SC | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `RCA-01` | P-101A Suction Starvation & Cavitation Trip | `PLAUSIBLE_HYPOTHESIS` | 100% | 100% | 100% | 50482.1 ms |
| `RCA-02` | K-101 Centrifugal Compressor Overheat & ESD Trip | `PLAUSIBLE_HYPOTHESIS` | 100% | 100% | 100% | 52702.0 ms |
| `RCA-03` | P-101A Missing Evidence Honest Abstention Gate | `PLAUSIBLE_HYPOTHESIS` | 100% | 100% | 100% | 80558.8 ms |
| `RCA-04` | Out-of-Distribution (OOD) Nonexistent Asset Safety Gate | `ASSET_NOT_FOUND` | 100% | 100% | 100% | 573.3 ms |
| `RCA-05` | Final-Step Protocol Tool Lockout & Safe Interception | `PLAUSIBLE_HYPOTHESIS` | 100% | 100% | 100% | 56082.4 ms |

## Architectural Remediations Verified

1. **Destructive Finalizer Elimination:** The legacy prompt overwriter that erased grounded evidence with `No root cause is confirmed from the symptom-only information provided` has been replaced by the deterministic `RCAEvidenceValidator`.
2. **Final-Step Tool Lockout:** Synthesis steps strictly prohibit tool calls in system instructions, candidate tool lists, and runtime execution. Any rogue `ToolCallProposal` is intercepted and safely converted to a `FinalAnswer`.
3. **Multi-Channel Evidence Acquisition:** Text, visual P&ID, and plant topology graphs are retrieved concurrently into an authoritative `RCAEvidenceBundle` with stable `[E1]`, `[E2]` citation identifiers.
4. **Fail-Closed OOD Protection:** Unregistered equipment tags (such as `K-888`) fail closed with `ASSET_NOT_FOUND` before entering expensive or hallucination-prone generation loops.
5. **Sensor Resolution:** Refinery equipment tags resolve deterministically to valid sensor IDs (e.g., `P-101A` → `PT-101`, `K-101` → `TT-204`), eliminating default-sensor parameter bugs.