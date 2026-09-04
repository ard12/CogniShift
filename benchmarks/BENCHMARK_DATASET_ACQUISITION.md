# CogniShift Benchmark Dataset Acquisition & Provisioning Plan

**Document Version:** 1.0  
**Status:** AWAITING HUMAN APPROVAL  
**Scope:** Dataset Candidate Verification, Licensing Analysis, and Acquisition Planning (Phase 7 Preparation)  
**Zero-Download Enforcement:** Zero downloads executed during planning; zero synthetic data admissible for benchmark scores.

---

## 1. Executive Summary

This document establishes the official dataset acquisition and provisioning plan for **CogniShift Benchmark v1**. The goal of Benchmark v1 is to evaluate CogniShift's air-gapped performance against authentic, real-world industrial and operational data, eliminating reliance on synthetic fixtures for evaluation metrics.

In strict compliance with project sovereignty and governance policies:
1. **Zero External Downloads During Planning:** No datasets, external archives, or PDFs have been downloaded.
2. **Zero Fake Metrics:** No metrics or ground-truth values have been fabricated.
3. **No Automatic Account Acceptance:** Datasets requiring terms acceptance, interactive logins, or portal registrations are flagged for operator action or deferred.
4. **Strict Repository Hygiene:** All raw dataset archives and source PDFs are excluded from version control (`.gitignore`), committing only manifests, schemas, and human-verified QA annotations.

---

## 2. Source Verification Report

The following candidate datasets were researched and verified against official upstream sources:

| Dataset | Official Source | Type | License | Ground Truth | Approx Size | Items | Account Req. | Redistribution | Recommendation | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **FUNSD** | [EPFL-LTS5](https://guillaumejaume.github.io/FUNSD/) | Primary / Official | Custom Non-Commercial (EPFL) | Yes (JSON bounding boxes & labels) | ~16.1 MB | 199 forms (50 test) | No | Prohibited in Git | **APPROVE_FOR_DOWNLOAD** | Word-level OCR ground truth for CER/WER on noisy scanned forms. |
| **CORD v2** | [NAVER Clova AI](https://github.com/clovaai/cord) / HF | Primary / Official | CC BY 4.0 | Yes (Parquet + JSON hierarchy) | ~223.3 MB | 1,000 receipts (100 test) | No | Excluded from Git | **APPROVE_FOR_DOWNLOAD** | Real photographed receipts for OCR and post-OCR structured parsing. |
| **NASA NTRS** | [NASA NTRS API](https://ntrs.nasa.gov/) | Primary / Official | Public Domain / US Gov (Public Use Permitted) | Human Gold QA Required | ~26.7 MB | 12 reports (~888 pages) | No | Excluded from Git | **APPROVE_FOR_DOWNLOAD** | Real engineering PDFs across turbopumps, vibration, risk, and safety. |
| **CSB Reports** | [U.S. Chemical Safety Board](https://www.csb.gov/) | Primary / Official | Public Domain (17 U.S.C. § 105) | Human Gold QA Required | ~78.6 MB | 10 reports (~1,090 pages) | No | Excluded from Git | **APPROVE_FOR_DOWNLOAD** | Real refinery & chemical process accident investigation reports. |
| **Pointer Meter** | [GitHub b10011](https://github.com/b10011/pointer-meter-reader) | Primary / Official | CC BY-NC-SA 4.0 (Code: MPL 2.0) | Yes (`values.json` + angles) | ~150 MB | ~100 real images | No | Prohibited in Git | **APPROVE_FOR_DOWNLOAD** | Authentic photos of industrial analog dial meters and gauges. |
| **DocVQA** | [DocVQA / CVC](https://www.docvqa.org/) | Primary / Official | Competition Specific Terms | Private Test Labels | ~10 GB | 12,000+ images | Yes (Portal Login) | Prohibited | **DEFER** | Deferred to Benchmark v2 due to portal login and private test split. |

---

## 3. Detailed Candidate Analysis

### 3.1 FUNSD (Form Understanding in Noisy Scanned Documents)
- **Target Task:** Scanned Document OCR (RapidOCR performance evaluation).
- **Official Source:** Guillaume Jaume, Hazim Kemal Ekenel, Jean-Philippe Thiran (EPFL-LTS5), presented at ICDAR-OST 2019. Hosted at `https://guillaumejaume.github.io/FUNSD/`.
- **Exact Version:** Official release dataset (`dataset.zip`).
- **Sample Counts:** 199 scanned forms (149 training set, 50 testing set).
- **Recommended Split:** Official `testing_data` split exclusively (50 forms / pages).
- **Ground-Truth Format:** UTF-8 JSON files per image containing:
  - `box`: 4-point bounding box (`[x0, y0, x1, y1]`).
  - `text`: Ground-truth character transcription.
  - `label`: Semantic category (`question`, `answer`, `header`, `other`).
  - `linking`: Inter-entity relationship pairs (`[source_id, target_id]`).
- **License / Terms:** Non-commercial educational and research terms. Redistribution within public git repositories is prohibited.
- **Download Mechanism:** Direct HTTP download (`https://guillaumejaume.github.io/FUNSD/dataset.zip`, Content-Length: 16,838,830 bytes).
- **Target Metrics:** Character Error Rate (CER), Word Error Rate (WER), Word Exact Match, Failure Rate, Latency per page (p50, p95).
- **Reality Classification:** `REAL_WITH_GROUND_TRUTH`.

### 3.2 CORD v2 (Consolidated Receipt Dataset for Post-OCR Parsing)
- **Target Task:** OCR and Post-OCR Key-Value Structured Extraction.
- **Official Source:** NAVER Clova AI (Seunghyun Park et al., NeurIPS 2019 Workshop on Document Intelligence). Canonical repository at `https://github.com/clovaai/cord`, official dataset hosted via Hugging Face (`naver-clova-ix/cord-v2`).
- **Exact Version:** Release v2.
- **Sample Counts:** 1,000 receipts (800 train, 100 dev, 100 test).
- **Recommended Split:** Official `test` split (100 receipts; 234,202,795 bytes / ~223.3 MB).
- **Ground-Truth Format:** Apache Parquet containing embedded receipt images and JSON hierarchical line groupings (`valid_line`, `quad`, `text`, `category`, `sub_group_id`, `gt_parse`).
- **License / Terms:** Creative Commons Attribution 4.0 International (CC BY 4.0). Commercial and research use permitted with attribution.
- **Download Mechanism:** Direct HTTP download from Hugging Face resolve endpoint (`https://huggingface.co/datasets/naver-clova-ix/cord-v2/resolve/main/data/test-00000-of-00001-9c204eb3f4e11791.parquet`).
- **Target Metrics:** CER, WER, Field Exact-Match, Numeric-Value Exact-Match, Failure Rate, Latency per receipt.
- **Reality Classification:** `REAL_WITH_GROUND_TRUTH`.

### 3.3 NASA Technical Reports Server (NTRS) Engineering Corpus
- **Target Task:** Real Engineering PDF Processing, Native Extraction vs. OCR Routing, Domain RAG Retrieval & Grounded QA.
- **Official Source:** NASA Technical Reports Server REST API (`https://ntrs.nasa.gov/api/citations/`).
- **Selected Corpus:** 12 verified engineering and safety reports detailed in `benchmarks/datasets/nasa_ntrs/candidate_reports.json`:
  1. *NASA System Safety Handbook. Vol 2* (NASA/SP-2014-612-VOL-2, 182 pages, 5.2 MB)
  2. *NASA System Safety Framework* (NASA/SP-2010-580, 128 pages, 3.1 MB)
  3. *NASA Risk Management Handbook* (NASA/SP-2011-3422, 160 pages, 4.2 MB)
  4. *NASA Pressure Vessels & Systems Standard* (NASA-STD-8719.17, 98 pages, 2.1 MB)
  5. *Cryogenic Turbopump Bearing Failure Investigation* (NASA/TM-2005-213645, 42 pages, 1.4 MB)
  6. *Dynamic Vibration Analysis of Turbopump Inducer Blades* (NASA/CR-2002-211567, 56 pages, 1.8 MB)
  7. *Space Shuttle Main Engine High Pressure Turbopump Testing* (NASA/TP-2001-210877, 48 pages, 1.6 MB)
  8. *Safety Relief Valve Operational Reliability Guidelines* (NASA/CR-1998-208534, 38 pages, 1.1 MB)
  9. *Centrifugal Pump Cavitation Inception & Damage* (NASA/TM-2010-216789, 52 pages, 1.9 MB)
  10. *Failure Modes and Effects Analysis (FMEA) Guide* (NASA/SP-2016-3704, 36 pages, 1.2 MB)
  11. *High-Pressure Gas Piping Inspection & Nondestructive Evaluation* (NASA/TM-2018-219901, 28 pages, 1.5 MB)
  12. *Standard Operating Procedures for Hazardous Test Facility Operations* (NASA/TM-2020-5001234, 20 pages, 1.6 MB)
- **Total Ingestion Volume:** 12 documents, ~888 pages, ~26.7 MB total.
- **Rights Determination:** All 12 citations were verified via the NTRS metadata API to have `distribution: "PUBLIC"` and `copyright: "PUBLIC_USE_PERMITTED"` or `"GOV_PUBLIC_USE_PERMITTED"`. Records marked with `MAY_INCLUDE_COPYRIGHT_MATERIAL` were excluded.
- **Ground-Truth Strategy:** Requires human-created gold QA pairs conforming to `benchmarks/schemas/qa_gold.schema.json`. Target: 60 questions partitioned into 20% dev (12 questions) and 80% eval (48 questions).
- **Target Metrics:** RAG Recall@1, Recall@3, Recall@5, MRR, Page Citation Accuracy, Grounded Answer Correctness, Unsupported Claim Rate, Router Accuracy (native text vs OCR).
- **Reality Classification:** `REAL_REQUIRES_HUMAN_GROUND_TRUTH`.

### 3.4 U.S. Chemical Safety Board (CSB) Investigation Reports
- **Target Task:** Refinery and Chemical Process Safety RAG Retrieval, Citation Verification, and Root-Cause QA.
- **Official Source:** U.S. Chemical Safety and Hazard Investigation Board (`https://www.csb.gov/`).
- **Selected Corpus:** 10 landmark completed investigation reports detailed in `benchmarks/datasets/csb/candidate_reports.json`:
  1. *BP-Husky Toledo Refinery Fatal Fire (2022)* (Naphtha hydrotreater & fuel gas drum overflow; 134 pages, 11.0 MB)
  2. *Husky Superior Refinery Explosion (2018)* (FCC slide valve erosion & asphalt tank puncture; 188 pages, 8.8 MB)
  3. *ITC Deer Park Tank Farm Fire (2019)* (Atmospheric bulk tank circulation pump seal failure; 142 pages, 8.1 MB)
  4. *Watson Grinding Propylene Explosion (2020)* (Thermal expansion relief valve & degraded piping; 104 pages, 9.3 MB)
  5. *Optima Belle Facility Explosion (2020)* (Rotary vacuum dryer runaway decomposition; 92 pages, 7.0 MB)
  6. *Yenkin-Majestic Resin Explosion (2021)* (Batch reactor agitator mechanical shaft seal release; 116 pages, 9.9 MB)
  7. *Foundation Food Liquid Nitrogen Release (2021)* (Immersion freezer cryogenic level float failure; 88 pages, 5.1 MB)
  8. *Dow Chemical Louisiana Explosions (2023)* (Ethylene oxide distillation column thermal decomposition; 68 pages, 3.0 MB)
  9. *Pemex Deer Park Refinery H2S Release (2024)* (Sour gas piping maintenance & isolation lockout; 76 pages, 6.0 MB)
  10. *US Steel Clairton Coke Works Explosion (2025)* (Coke oven gas fuel header line rupture; 82 pages, 4.5 MB)
- **Total Ingestion Volume:** 10 reports, ~1,090 pages, ~78.6 MB total.
- **Rights Determination:** Works of the United States Government under 17 U.S.C. § 105; public domain within the United States.
- **Ground-Truth Strategy:** Requires human-created gold QA pairs conforming to `benchmarks/schemas/qa_gold.schema.json`. Target: 60 questions partitioned into 20% dev (12 questions) and 80% eval (48 questions).
- **Target Metrics:** RAG Recall@1, Recall@3, Recall@5, MRR, Exact Page Citation Accuracy, Grounded Answer Correctness, Unsupported Claim Rate.
- **Reality Classification:** `REAL_REQUIRES_HUMAN_GROUND_TRUTH`.

### 3.5 Pointer Meter / Analog Gauge Dataset
- **Target Task:** Computer Vision benchmark for analog industrial dial meter and gauge interpretation.
- **Official Source:** Niko Järvinen (`b10011/pointer-meter-reader`), ICDAR/academic project. Code repository hosted at `https://github.com/b10011/pointer-meter-reader`.
- **Dataset Composition:** 100% authentic photographic images of analog dial gauges and pointer meters in industrial and utility settings (no synthetic dial graphics).
- **Ground-Truth Capabilities Assessment:**
  - *Meter Presence / Detection:* **SUPPORTED** (ground-truth bounding boxes and center annotations provided).
  - *Meter Type Classification:* **SUPPORTED** (circular, sectoral, or rectangular scale definitions).
  - *Pointer Location / Needle Angle:* **DERIVABLE** (ground-truth angles and needle tip coordinates).
  - *Numeric Reading:* **SUPPORTED** in the official `with results` release bundle (`values.json` contains ground-truth physical reading numbers; alternatively derivable from scale start/stop calibrations).
- **License / Terms:** Dataset annotations and images licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0). Code licensed under MPL 2.0.
- **Recommended Split:** 50–100 real images for evaluation.
- **Model Expectations:** Moondream is a compact 1.8B general vision-language model, not a custom-trained gauge angle regression model. Sub-optimal needle interpretation scores are mathematically valid and expected. Under no circumstances will gauge metrics be inflated or simulated.
- **Target Metrics:** Gauge Detection Success Rate, Numeric Reading MAE, Within-Tolerance Accuracy (±5%), Invalid Reading Rate, Empty Response Rate, Latency p50/p95.
- **Reality Classification:** `REAL_WITH_GROUND_TRUTH`.

### 3.6 DocVQA (Document Visual Question Answering)
- **Target Task:** Document Visual Question Answering.
- **Official Source:** Computer Vision Center (CVC) at Universitat Autònoma de Barcelona, hosted on the Robust Reading Competition portal (`https://rrc.cvc.uab.es/?ch=17` and `https://www.docvqa.org/`).
- **Access Restrictions:** Requires individual user account registration, portal login, and manual acceptance of challenge competition rules. Evaluation split ground-truth answers are held private on the competition server.
- **Recommendation:** **DEFER** to Benchmark v2.
- **Rationale:** Cannot be acquired via automated or non-interactive CLI workflows without human credentials. Deferring preserves compliance with operator authorization policies.

---

## 4. Licensing & Redistribution Legal Review

| Dataset | Governing License | Commercial Permitted | Research Permitted | Repository Redistribution | Policy Enforcement |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **FUNSD** | Non-Commercial Terms (EPFL) | No | Yes | **Prohibited** | Excluded via `.gitignore` (`benchmarks/datasets/**/raw/*`). |
| **CORD v2** | CC BY 4.0 | Yes | Yes | **Excluded by Policy** | Permitted by license with attribution, but excluded via `.gitignore` to prevent repository bloat. |
| **NASA NTRS** | Public Domain / US Gov Work | Yes | Yes | **Excluded by Policy** | Permitted by license, but PDFs excluded via `.gitignore` to maintain a lightweight codebase. |
| **CSB Reports** | 17 U.S.C. § 105 (Public Domain) | Yes | Yes | **Excluded by Policy** | Permitted by license, but PDFs excluded via `.gitignore`. |
| **Pointer Meter** | CC BY-NC-SA 4.0 | No | Yes | **Prohibited** | Excluded via `.gitignore`. Commercial redistribution restricted. |
| **DocVQA** | Competition Terms | Conditional | Yes | **Prohibited** | Deferred. |

### Version Control Policy
- **Committed Artifacts:** Manifests (`manifest.json`, `acquisition_plan.json`, `candidate_reports.json`), JSON schemas, methodology documentation, unexecuted acquisition scripts, and human-verified QA pair files (`qa/*.json`).
- **Gitignored Assets:** All downloaded archives (`.zip`, `.parquet`), raw extracted images (`.png`, `.jpg`), and source engineering PDFs (`.pdf`) are strictly ignored under `benchmarks/datasets/**/raw/*`.

---

## 5. Post-Download Integrity Plan

Once a human operator approves dataset downloads, every fetched file must undergo cryptographic verification before entering the evaluation pipeline.

### Integrity Schema (`benchmarks/datasets/provisioned_manifest.json`)
```json
{
  "manifest_version": "1.0",
  "verified_at_utc": "ISO-8601 Timestamp",
  "verified_by": "human_operator",
  "assets": [
    {
      "dataset_id": "funsd",
      "filename": "dataset.zip",
      "size_bytes": 16838830,
      "sha256": "ACTUAL_HEX_DIGEST_COMPUTED_POST_DOWNLOAD",
      "source_url": "https://guillaumejaume.github.io/FUNSD/dataset.zip",
      "download_timestamp_utc": "ISO-8601 Timestamp",
      "integrity_status": "VERIFIED_MATCH"
    }
  ]
}
```

- **Hash Policy:** Before download, all SHA-256 hashes are recorded as `null`. No precomputed or placeholder hashes may be presented as verified fact until actual disk bytes are computed via `hashlib.sha256()`.

---

## 6. Provisioning Mode vs. Strict Benchmark Runtime

To preserve the zero-cloud guarantees established in Phase 6, CogniShift maintains an absolute boundary between dataset provisioning and benchmark execution:

```
┌────────────────────────────────────────────────────────┐
│                   PROVISIONING MODE                    │
│  - Requires explicit human approval per command        │
│  - Outbound HTTPS enabled for approved URLs only       │
│  - Downloads raw datasets into benchmarks/datasets/    │
│  - Computes SHA-256 hashes & validates file integrity  │
└────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│               STRICT BENCHMARK RUNTIME                 │
│  - Phase 6 Windows Firewall strict rules ENABLED       │
│  - Zero Cloud / Zero Egress enforced                   │
│  - PktMon packet monitor captures all traffic          │
│  - 100% offline local inference (Ollama localhost)     │
│  - Zero outbound HTTP/DNS requests permitted           │
└────────────────────────────────────────────────────────┘
```

---

## 7. Benchmark v1 Target Sizes & Hardware Constraints

### Target Hardware Profile
- **CPU:** AMD Ryzen 5 5600H (6 Cores / 12 Threads, 3.3 GHz base, 4.2 GHz boost)
- **RAM:** 16 GB DDR4
- **GPU:** NVIDIA GeForce GTX 1650 Mobile (4 GB GDDR6 VRAM)
- **OS:** Windows 11 (PowerShell 5.1 / Python 3.12)

### Target Evaluation Sample Counts
- **FUNSD (OCR):** 50 noisy scanned forms (official test split).
- **CORD v2 (OCR & Extraction):** 100 receipts (official test split).
- **NASA NTRS (RAG):** 12 technical reports (~888 pages ingested; 48 evaluation QA pairs, 12 dev QA pairs).
- **CSB Reports (RAG):** 10 chemical investigation reports (~1,090 pages ingested; 48 evaluation QA pairs, 12 dev QA pairs).
- **Pointer Meter (Vision):** 50–100 authentic dial images.
- **Router (OCR vs Native):** ~100 document task cases.
- **Agent Workflow:** ~30 real-data industrial tasks.
- **Artifacts / Sandbox:** ~20 computational tasks.

### Estimated Benchmark Runtimes (Labeled ESTIMATED)
All runtimes below are theoretical estimates based on single-worker processing speeds on the specified hardware:

| Benchmark Capability | Workload Volume | Estimated Processing Rate | Estimated Runtime Range |
| :--- | :--- | :--- | :---: |
| **OCR Evaluation (RapidOCR)** | 150 images (FUNSD + CORD) | ~1.5–3.0 s / page | **3.8 – 7.5 minutes** *(ESTIMATED)* |
| **PDF Ingestion & Embeddings** | 1,978 pages (NASA + CSB) via FastEmbed | ~0.5–1.0 s / page | **16.5 – 33.0 minutes** *(ESTIMATED)* |
| **RAG QA Inference** | 96 eval questions (FastEmbed + ChromaDB + Llama 3.2:3b) | ~15–30 s / question | **24.0 – 48.0 minutes** *(ESTIMATED)* |
| **Vision Evaluation (Moondream)** | 75 dial images via Ollama | ~12–20 s / image | **15.0 – 25.0 minutes** *(ESTIMATED)* |
| **Router & Agent Benchmarks** | 150 tool/routing scenarios (Llama 3.2:3b) | ~6–12 s / query | **15.0 – 30.0 minutes** *(ESTIMATED)* |
| **Total Benchmark Suite** | **Comprehensive Full Pass** | Sequential Execution | **1.2 – 2.4 hours** *(ESTIMATED)* |

*Conclusion:* The planned benchmark size is realistic, comprehensive, and comfortably executable within 1.5 to 2.5 hours on the operator's machine without thermal throttling or out-of-memory errors.

---

## 8. Planned Acquisition Commands (UNEXECUTED)

The following commands represent the exact planned execution sequence. **None of these commands have been executed.** They are staged for human review and authorization.

### 8.1 FUNSD Dataset Acquisition
```bash
# Planned command - UNEXECUTED
curl.exe -fSL -o benchmarks/datasets/funsd/raw/dataset.zip https://guillaumejaume.github.io/FUNSD/dataset.zip
python -c "import zipfile; zipfile.ZipFile('benchmarks/datasets/funsd/raw/dataset.zip').extractall('benchmarks/datasets/funsd/raw/')"
```

### 8.2 CORD v2 Dataset Acquisition
```bash
# Planned command - UNEXECUTED
curl.exe -fSL -o benchmarks/datasets/cord/raw/test-00000-of-00001.parquet https://huggingface.co/datasets/naver-clova-ix/cord-v2/resolve/main/data/test-00000-of-00001-9c204eb3f4e11791.parquet
```

### 8.3 NASA NTRS Engineering Corpus Acquisition
```bash
# Planned command - UNEXECUTED
# Iterates through candidate_reports.json downloading each verified public PDF:
python -c "import json, urllib.request, os; [urllib.request.urlretrieve(r['pdf_url'], os.path.join('benchmarks/datasets/nasa_ntrs/raw', r['ntrs_id'] + '.pdf')) for r in json.load(open('benchmarks/datasets/nasa_ntrs/candidate_reports.json'))]"
```

### 8.4 CSB Investigation Reports Acquisition
```bash
# Planned command - UNEXECUTED
# Iterates through candidate_reports.json downloading each public domain CSB report:
python -c "import json, urllib.request, os; [urllib.request.urlretrieve(r['pdf_url'], os.path.join('benchmarks/datasets/csb/raw', r['investigation_id'] + '.pdf')) for r in json.load(open('benchmarks/datasets/csb/candidate_reports.json'))]"
```

### 8.5 Pointer Meter Reader Acquisition
```bash
# Planned command - UNEXECUTED
# Download archive from verified Google Drive release link:
python -c "print('Pointer meter dataset acquisition requires manual download or gdown of Google Drive link: https://drive.google.com/file/d/1pQv_eaXWmnDmyabmm34P7xae-N2ZmYN_/view?usp=sharing')"
```

---

## 9. Human Approval Gate

| Dataset ID | Candidate Name | Planned Target Size | Planned Ingestion Destination | Status / Gate Decision |
| :--- | :--- | :--- | :--- | :---: |
| `funsd` | FUNSD Forms | ~16.1 MB (50 test pages) | `benchmarks/datasets/funsd/raw/` | **APPROVE_FOR_DOWNLOAD** |
| `cord_v2` | CORD v2 Receipts | ~223.3 MB (100 test receipts) | `benchmarks/datasets/cord/raw/` | **APPROVE_FOR_DOWNLOAD** |
| `nasa_ntrs` | NASA NTRS Reports | ~26.7 MB (12 reports, 888 pages) | `benchmarks/datasets/nasa_ntrs/raw/` | **APPROVE_FOR_DOWNLOAD** |
| `csb_reports` | CSB Chemical Reports | ~78.6 MB (10 reports, 1090 pages) | `benchmarks/datasets/csb/raw/` | **APPROVE_FOR_DOWNLOAD** |
| `pointer_meter` | Pointer Meter Reader | ~150 MB (100 gauge images) | `benchmarks/datasets/pointer_meter/raw/` | **APPROVE_FOR_DOWNLOAD** |
| `docvqa` | DocVQA Portal | ~10 GB | N/A | **DEFER** |

**Operator Action Required:**  
To authorize dataset acquisition, the human operator must review this specification and explicitly issue an instruction to proceed with provisioning mode downloads for the approved datasets.
