# CogniShift Benchmark Suite

This directory contains the specification, schemas, dataset manifests, and evaluation methodology for the **CogniShift Real-Data Benchmark Suite (Benchmark v1)**.

---

## 1. Directory Structure

```
benchmarks/
├── README.md                           # This document: benchmark overview and directory guide
├── BENCHMARK_METHODOLOGY.md            # Comprehensive benchmark principles, split strategy, and metric formulas
├── BENCHMARK_DATASET_ACQUISITION.md    # Source verification report, legal review, and acquisition plan
├── schemas/
│   ├── qa_gold.schema.json             # Strict schema for human-verified Q&A evaluation pairs
│   └── raw_result.schema.json          # Schema for line-delimited raw execution logs (JSONL)
├── datasets/
│   ├── manifest.json                   # Master registry of candidate datasets and status
│   ├── acquisition_plan.json           # Machine-readable plan of download URLs, licenses, and commands
│   ├── funsd/
│   │   ├── raw/                        # Target directory for FUNSD downloads (gitignored)
│   │   └── processed/                  # Normalized OCR evaluation inputs
│   ├── cord/
│   │   ├── raw/                        # Target directory for CORD v2 downloads (gitignored)
│   │   └── processed/                  # Extracted receipt images and ground truth
│   ├── nasa_ntrs/
│   │   ├── candidate_reports.json      # 12 verified NASA engineering reports (~888 pages)
│   │   ├── raw/                        # Target directory for downloaded NASA PDFs (gitignored)
│   │   ├── metadata/                   # Report metadata and rights records
│   │   └── qa/                         # Human-verified gold Q&A pairs (qa_gold.schema.json)
│   ├── csb/
│   │   ├── candidate_reports.json      # 10 verified CSB accident investigation reports (~1,090 pages)
│   │   ├── raw/                        # Target directory for downloaded CSB PDFs (gitignored)
│   │   ├── metadata/                   # Incident metadata and timeline records
│   │   └── qa/                         # Human-verified gold Q&A pairs (qa_gold.schema.json)
│   └── pointer_meter/
│       ├── raw/                        # Target directory for Pointer Meter reader images (gitignored)
│       └── processed/                  # Calibrated dial annotations and ground-truth values
├── runners/                            # Future benchmark execution scripts (Phase 7)
└── results/                            # Raw JSONL execution logs and aggregate reports (gitignored)
```

---

## 2. Core Benchmark Principles

1. **Authentic Data Exclusively:** All benchmark evaluations must execute against authentic scanned documents, technical reports, and photographs. Synthetic fixtures in `data/manuals/` and `data/vision_test/` are restricted to regression tests.
2. **Zero Fabrication:** No benchmark metrics or ground-truth answers may be manufactured or assumed.
3. **Failures Count as Failures:** Exceptions, timeouts, and unparseable responses are scored as errors in the metric denominator.
4. **Air-Gapped Execution:** Benchmark evaluation runs occur with Phase 6 Windows Firewall rules active and PktMon packet monitoring enabled.

---

## 3. Dataset Acquisition Status

Dataset provisioning is currently **AWAITING HUMAN APPROVAL**.

| Dataset ID | Capability | Status | Source | License | Expected Size |
| :--- | :--- | :--- | :--- | :--- | :---: |
| `funsd` | OCR (Noisy Scanned Forms) | Awaiting Approval | EPFL-LTS5 | Non-Commercial | ~16.1 MB |
| `cord_v2` | OCR & Structured Extraction | Awaiting Approval | NAVER Clova AI | CC BY 4.0 | ~223.3 MB |
| `nasa_ntrs` | Domain RAG & PDF Ingestion | Awaiting Approval | NASA NTRS API | Public Domain / US Gov | ~26.7 MB |
| `csb_reports` | Industrial Chemical RAG | Awaiting Approval | U.S. CSB | Public Domain (17 U.S.C. 105) | ~78.6 MB |
| `pointer_meter` | Vision (Analog Dial Gauges) | Awaiting Approval | GitHub (b10011) | CC BY-NC-SA 4.0 | ~150 MB |
| `docvqa` | Visual Document QA | DEFERRED (v2) | CVC / RRC | Competition Terms | ~10 GB |

See [`BENCHMARK_DATASET_ACQUISITION.md`](BENCHMARK_DATASET_ACQUISITION.md) for full verification details and planned commands.

---

## 4. Current Phase Status

```
PHASE 6 STATUS: FROZEN / VERIFIED
REAL-DATA BENCHMARK DESIGN: COMPLETE
DATASET ACQUISITION: AWAITING HUMAN APPROVAL
DATASETS DOWNLOADED: 0
BENCHMARK RUNS EXECUTED: 0
PHASE 7: LOCKED
```
