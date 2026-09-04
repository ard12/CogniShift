# CogniShift Benchmark Methodology (Benchmark v1)

## 1. Core Benchmark Principle

The CogniShift Benchmark measures actual system performance on real-world data under strict, reproducible, and air-gapped operating conditions.

- **Real Data Imperative:** Only authentic documents, forms, reports, and photographic images are admissible in benchmark evaluations.
- **Strict Separation of Synthetic Fixtures:** Unit test fixtures, programmatically generated PDF forms (e.g. FPDF/ReportLab), synthetic sensor tables, or programmatic gauge graphics are strictly reserved for functional regression and security policy verification. They are never reported as real-world benchmark metrics.
- **Zero Fabrication Posture:** If genuine ground truth is absent for a candidate dataset, the task is formally categorized as `NOT BENCHMARKABLE WITH CURRENT SOURCE` or `HUMAN GROUND-TRUTH CREATION REQUIRED`. Metric values are never fabricated, approximated, or imputed.
- **Failures Count as Failures:** Benchmark runs that fail, timeout, throw uncaught exceptions, or generate unparseable responses are penalizingly scored as failures in the metric denominator.

---

## 2. Dataset Reality Classification

Every dataset considered for CogniShift benchmarking must receive one of five explicit classifications before ingestion:

| Classification | Definition | Admissibility for Benchmark v1 |
| :--- | :--- | :---: |
| `REAL_WITH_GROUND_TRUTH` | Real-world data paired with verified, pre-existing human ground-truth labels from the original authors. | **Admissible** (e.g. FUNSD, CORD v2, Pointer Meter) |
| `REAL_REQUIRES_HUMAN_GROUND_TRUTH` | Genuine real-world technical or regulatory documents without native QA pairs. Requires human ground-truth curation. | **Admissible with Human Audit** (e.g. NASA NTRS, CSB Reports) |
| `MIXED` | Datasets combining real photographic captures with synthetic or semi-synthetic annotations or overlays. | **Conditional** (must isolate real subsets) |
| `SYNTHETIC` | Programmatically generated or simulated text, forms, or imagery. | **Inadmissible for Benchmark Scores** (Restricted to regression unit tests) |
| `NOT_SUITABLE` | Data with ambiguous provenance, unverified licensing, or incompatible technical formats. | **Inadmissible** |

---

## 3. Train / Development / Evaluation Split Strategy

To prevent prompt tuning contamination and overfitting to benchmark items, all custom QA benchmarks adhere to strict split hygiene:

- **Split Ratio:** 20% Development split (`dev`), 80% Final Evaluation split (`eval`).
- **Deterministic Partitioning:** Random assignment using a fixed seed (`seed = 42`).
- **Freezing Rule:** Once the evaluation split is populated and human-verified, it is immutable. Prompts, retrieval chunking strategies, or model parameters may only be tuned against the `dev` split.
- **No Performance-Based Exclusions:** If CogniShift fails an item in the `eval` split, that item cannot be modified, rephrased, or deleted. Failures remain permanent evaluation results.

---

## 4. Human-Created Gold QA Workflow (NASA NTRS & CSB)

Neither NASA NTRS nor CSB investigation reports provide native QA pairs. To benchmark RAG retrieval accuracy and grounded question answering, a formal human annotation workflow is established:

```
[Real PDF Ingestion]
        │
        ▼
[Candidate Generation] ──► (Human Domain Expert OR Assisted LLM Draft)
        │
        ▼
[Audit & Verification] ──► (Human Operator verifies page citation, excerpt, and answer)
        │
        ├──► Status: "rejected" ──────► Excluded from benchmark
        └──► Status: "human_verified" ──► Partitioned into dev (20%) / eval (80%)
```

### 4.1 Schema Compliance
All generated QA items must strictly validate against [`benchmarks/schemas/qa_gold.schema.json`](schemas/qa_gold.schema.json). Required attributes include:
- `question_id`: Globally unique identifier (`NASA-001`, `CSB-014`).
- `question`: Natural language question unambiguous to a human technical reader.
- `normalized_answer`: Canonical ground-truth answer string.
- `accepted_answers`: Array of valid lexical variants or equivalent numeric units.
- `document_id`: Corpus document reference.
- `relevant_pages`: Array of 1-indexed page numbers containing the direct factual evidence.
- `supporting_excerpt_reference`: Exact verbatim excerpt from the document text justifying the answer.
- `question_type`: Structural cognitive category.
- `difficulty`: Assessed complexity (`EASY`, `MEDIUM`, `HARD`).
- `verification_status`: Strictly `human_verified`.

### 4.2 Target Question Mix (~60 NASA, ~60 CSB)
Questions must reflect operational industrial inquiries across 10 defined categories:

| Category | Description | Target Share |
| :--- | :--- | :---: |
| `FACT_LOOKUP` | Direct extraction of stated technical parameters (e.g. design pressure, fluid type). | ~15% |
| `NUMERIC` | Quantities, tolerances, sensor readings, dimensions, or thresholds with units. | ~15% |
| `CAUSE` | Root-cause explanations of mechanical, electrical, or chemical failures. | ~15% |
| `SEQUENCE` | Chronological order of upset events, alarms, or emergency responses. | ~10% |
| `RECOMMENDATION` | Formal corrective actions or safety recommendations issued. | ~10% |
| `EQUIPMENT` | Identification of specific plant equipment tags, valves, pumps, or vessels. | ~10% |
| `PROCEDURE` | Prescribed maintenance steps, permit requirements, or startup protocols. | ~10% |
| `FAILURE_MODE` | Specific engineering failure mechanisms (e.g. sulfidation, cavitation, fatigue). | ~5% |
| `MULTI_PAGE` | Questions whose answer requires synthesizing information across 2+ distinct pages. | ~5% |
| `CROSS_SECTION` | Comparison across separate report sections (e.g. Executive Summary vs Appendix). | ~5% |

---

## 5. Metric Formulas & Mathematical Definitions

All metric formulas are fixed prior to benchmark execution. For all metrics, failures (crashes, unhandled timeouts, empty returns) are retained in the denominator.

### 5.1 Character Error Rate (CER)
Measures OCR character-level transcription error against ground truth using Levenshtein edit distance:

$$\text{CER} = \frac{\sum_{i=1}^N \text{Levenshtein}_{\text{char}}(R_i, H_i)}{\sum_{i=1}^N |R_i|}$$

- $R_i$: Ground-truth reference character sequence for document $i$.
- $H_i$: OCR hypothesis character sequence produced by RapidOCR.
- $N$: Total number of evaluated documents/pages.
- **Edge Cases:** If $R_i$ is non-empty and $H_i$ is empty (OCR failure), edit distance equals $|R_i|$, resulting in 100% error for that item. If OCR completely crashes on page $i$, edit distance is assigned as $|R_i|$.

### 5.2 Word Error Rate (WER)
Measures OCR word-level error rate after whitespace/punctuation tokenization:

$$\text{WER} = \frac{\sum_{i=1}^N \text{Levenshtein}_{\text{word}}(R_i, H_i)}{\sum_{i=1}^N \text{Count}_{\text{words}}(R_i)}$$

### 5.3 Retrieval Recall@k
Measures whether the ground-truth relevant page(s) appear within the top-$k$ retrieved chunks returned by ChromaDB:

$$\text{Recall@}k = \frac{1}{Q} \sum_{q=1}^Q \mathbb{I}\left( \text{RelevantPages}(q) \cap \text{RetrievedPages}_k(q) \neq \emptyset \right)$$

- Evaluated for $k \in \{1, 3, 5\}$.
- If no chunks are retrieved or retrieval errors out, the indicator $\mathbb{I}$ evaluates to 0.

### 5.4 Mean Reciprocal Rank (MRR)
Evaluates the ranking quality of the first relevant chunk returned:

$$\text{MRR} = \frac{1}{Q} \sum_{q=1}^Q \frac{1}{\text{rank}_q}$$

- $\text{rank}_q$: 1-indexed position of the first retrieved chunk whose source metadata matches any page in $\text{RelevantPages}(q)$.
- If no relevant chunk appears in the retrieved results, $\frac{1}{\text{rank}_q} = 0$.

### 5.5 Grounded Answer Accuracy (Token F1 / Exact Match)
Evaluates generated answer text against `normalized_answer` and `accepted_answers`:
- **Exact Match (EM):** Binary 1 if normalized prediction matches any accepted answer string after lowercasing and punctuation stripping; 0 otherwise.
- **Token F1:** Standard harmonic mean of token-level precision and recall:

$$\text{Precision} = \frac{|T_{\text{pred}} \cap T_{\text{ref}}|}{|T_{\text{pred}}|}, \quad \text{Recall} = \frac{|T_{\text{pred}} \cap T_{\text{ref}}|}{|T_{\text{ref}}|}, \quad F_1 = \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

### 5.6 Mean Absolute Error (MAE) for Analog Gauge Reading
Measures pointer meter numeric estimation error on the Pointer Meter dataset:

$$\text{MAE} = \frac{1}{M} \sum_{m=1}^M \left| \hat{y}_m - y_m \right|$$

- $y_m$: Ground-truth physical gauge reading (e.g. bar, psi, °C).
- $\hat{y}_m$: Predicted reading extracted from local VLM (Moondream).
- **Failure Penalty:** If the model outputs an unparseable response, hallucinated text without a number, or fails to detect the gauge, the item is flagged as `invalid_reading_rate = 1` and excluded from numeric MAE but penalized in `gauge_completion_rate`.

### 5.7 Latency Percentiles (p50, p95)
Measured via high-resolution wall-clock timers (`time.perf_counter_ns`):
- Recorded in milliseconds per processed page, chunk, or inference turn.
- Sorted array: $p = \text{Percentile}(L, 50)$ and $p95 = \text{Percentile}(L, 95)$.

---

## 6. Anti-Cherry-Picking Protocol

1. **Frozen Manifest Registration:** Prior to test execution, the exact list of target sample IDs and SHA-256 digests is committed to git.
2. **Mandatory Exclusion Logging:** An evaluated item may only be excluded from the aggregate metric denominator if an explicit defect in the underlying source data is proven (e.g. corrupt image file that cannot be decoded by OpenCV/PIL, or provably erroneous ground truth).
3. **Audit Trail:** Any excluded item must be logged in `benchmarks/results/exclusions.json` detailing:
   - `item_id`
   - `exclusion_reason`
   - `approving_auditor`
   - `raw_exception`

---

## 7. Hardware Profile & Runtime Estimates

### 7.1 Tested Host Specification
- **CPU:** AMD Ryzen 5 5600H (6 Cores, 12 Threads, 3.30 GHz base / 4.20 GHz boost)
- **Host RAM:** 16.0 GB DDR4
- **GPU:** NVIDIA GeForce GTX 1650 Mobile (4.0 GB GDDR6 VRAM)
- **OS:** Windows 11 Home/Pro (Build 26200)

### 7.2 Estimated Benchmark Execution Times (ESTIMATED)
The benchmark sample counts are deliberately scaled to allow full completion within reasonable execution windows without memory exhaustion:

| Benchmark Suite | Evaluated Sub-tasks | Target Samples | Estimated Throughput | Estimated Runtime |
| :--- | :--- | :--- | :--- | :---: |
| **Document OCR** (FUNSD / CORD) | RapidOCR (CPU ONNX) | 150 pages | ~0.8s / page | ~2–3 minutes |
| **PDF Ingestion & Routing** | PyPDF text extraction | ~1,900 pages | ~25 pages / sec | ~1–2 minutes |
| **Vector Embedding** | FastEmbed (bge-small-en) | ~4,500 chunks | ~60 chunks / sec | ~2–3 minutes |
| **RAG Retrieval & QA** | ChromaDB + Llama 3.2 (3B) | 120 QA pairs | ~8s / QA pair | ~15–20 minutes |
| **Industrial Vision** | Moondream (4B VLM) | 75 images | ~4.5s / image | ~5–7 minutes |
| **HITL Agent Execution** | Local Engine Loop | 30 scenarios | ~12s / scenario | ~6–8 minutes |
| **Docker Sandbox** | Isolated Linux containers | 20 test runs | ~1.5s / run | ~1 minute |
| **Total Benchmark v1 Suite** | **All 7 capabilities** | **Full Benchmark** | **End-to-End** | **~35–50 minutes** |

*(Note: All execution times above are marked **ESTIMATED** based on baseline engine measurements. Actual runtimes will be recorded in empirical benchmark logs.)*
