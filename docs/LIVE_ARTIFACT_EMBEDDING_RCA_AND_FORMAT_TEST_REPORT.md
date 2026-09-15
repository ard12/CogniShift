# CogniShift Live Artifact Embedding RCA and Cross-Format Test Report

**Test date:** 2026-09-14  
**Application:** `https://localhost:8443/operator`  
**Workspace:** MRPL Operations Workspace, Workspace 1  
**Test identity:** Administrator  
**Source:** Knowledge Source `#10063`, `equipment_readings.csv`  
**Scope:** Live-browser verification of PNG chart generation and embedding into PPTX, PDF, and DOCX deliverables  
**Code changes made during this investigation:** None

## 1. Executive Result

The normal artifact workflow is not consistently embedding generated visualizations into requested documents.

| Request | Run | UI result | Package-level embedding result | Overall |
|---|---:|---|---|---|
| PPTX + PNG | `#101036` | Completed; PPTX `#1044` and PNG `#1043` | PPTX contains no media, pictures, native charts, or chart references | **FAIL** |
| PDF + PNG | `#101037` | Failed; PNG `#1045` only | Rejected staged PDF contains zero images and an orphan second page | **FAIL** |
| DOCX + PNG | `#101038` | Completed; DOCX `#1047` and PNG `#1046` | DOCX embeds `word/media/image1.png`; embedded SHA-256 exactly matches the generated PNG | **PASS** |
| DOCX + PDF + PNG | `#101039` | Failed overall; DOCX `#1049` and PNG `#1048`; PDF rejected | DOCX contains no media; staged PDF contains zero images | **FAIL** |
| PPTX + PDF + DOCX + PNG | `#101040` | Failed overall; DOCX `#1051` and PNG `#1050`; PDF rejected; PPTX missing | DOCX contains no media; staged PDF contains zero images; PPTX was never generated | **FAIL** |

Only the **DOCX-only** path successfully completed the entire source-to-chart-to-document embedding request.

## 2. Controlled Test Prompt

All successful-source tests used the same source and metric so results remained directly comparable:

```text
Using equipment_readings.csv in this workspace, create exactly one PNG line chart
of discharge_pressure_psi over timestamp. Create the requested document format and
embed that exact chart inside the document. Explain the trend and do not use
substitute columns or sources.
```

The requested format was changed per test to PDF, DOCX, DOCX+PDF, or PPTX+PDF+DOCX.

The chart pipeline consistently selected:

- Source: `2759dae9_equipment_readings.csv`
- Knowledge source: `#10063`
- X column: `timestamp`
- Y column: `discharge_pressure_psi`
- Transformation: `SELECT(timestamp, discharge_pressure_psi)`
- Rows: 576
- Chart type: line
- PNG size: 128,055 bytes
- PNG SHA-256: `F4253F9377EDBD2B2131F27CD6D5E87224F96EDE6B8A442C462170D1DFE26232`

## 3. Detailed Live-Browser Results

### Test A — PPTX and PNG

**Run:** `#101036`  
**Status shown in UI:** Completed  
**Generated artifacts:**

- `Presentation_equipment_readings.pptx`, Artifact `#1044`, 32,679 bytes
- `2759dae9_equipment_readings_discharge_pressure_psi_trend.png`, Artifact `#1043`, 128,055 bytes

The UI showed the chart preview and described the PPTX as `Enterprise Ready: True`.

Package inspection of the PPTX found:

- Four slides
- Zero `ppt/media/*` entries
- Zero `ppt/charts/*` entries
- Zero `<p:pic>` elements
- Zero `<p:graphicFrame>` elements
- Zero chart references

**Conclusion:** The PNG and PPTX were generated as separate artifacts, but the chart was not embedded in the presentation.

### Test B — PDF and PNG

**Run:** `#101037`  
**Status shown in UI:** Failed  
**Generated artifact:** PNG `#1045`  
**Missing required artifact:** PDF

The quality gate rejected the staged PDF with:

```text
PAGE_ORPHAN_DETECTED: Page 2 has only 1.0% vertical occupancy (orphaned row/snippet).
Rebalance pagination.
```

The staged PDF was 4,921 bytes and contained:

- Two pages
- Zero images on page 1
- Zero images on page 2
- Approximately 2,191 extracted text characters on page 1
- Only 71 extracted text characters on page 2

**Conclusion:** The chart was not embedded, and a pagination defect caused the document to fail acceptance completely.

### Test C — DOCX and PNG

**Run:** `#101038`  
**Status shown in UI:** Completed  
**Generated artifacts:**

- `Report_equipment_readings.docx`, Artifact `#1047`, 147,400 bytes
- PNG Artifact `#1046`, 128,055 bytes
- Quality report: `QREP-328F4A9A7BDC`

Package inspection found:

- `word/media/image1.png`
- One Word image relationship
- Embedded image size: 128,055 bytes
- Embedded image SHA-256: `F4253F9377EDBD2B2131F27CD6D5E87224F96EDE6B8A442C462170D1DFE26232`
- Generated chart SHA-256: `F4253F9377EDBD2B2131F27CD6D5E87224F96EDE6B8A442C462170D1DFE26232`

The hashes match exactly.

**Conclusion:** The DOCX-only path correctly embeds the generated chart.

### Test D — DOCX, PDF, and PNG

**Run:** `#101039`  
**Status shown in UI:** Failed overall  
**Generated artifacts:**

- DOCX Artifact `#1049`, 38,755 bytes, marked `Enterprise Ready: True`
- PNG Artifact `#1048`
- PDF rejected by the same orphan-page quality check

Package inspection of the accepted DOCX found:

- Zero `word/media/*` entries
- Zero image relationships

The staged PDF contained zero images.

**Conclusion:** The combined-format path does not attach the chart to either document. The DOCX is nevertheless incorrectly marked enterprise-ready.

### Test E — PPTX, PDF, DOCX, and PNG

**Run:** `#101040`  
**Status shown in UI:** Failed overall  
**Generated artifacts:**

- DOCX Artifact `#1051`, 38,756 bytes, marked `Enterprise Ready: True`
- PNG Artifact `#1050`
- PDF rejected
- PPTX not generated

The final goal-contract failure was:

```text
Required deliverables missing: pdf_deliverable, pptx_deliverable.
```

Package inspection of the DOCX again found no embedded media or image relationship. The staged PDF again contained no images.

**Conclusion:** When all formats are requested, format selection collapses the request into the DOCX+PDF path. PPTX is skipped, PDF fails, and the surviving DOCX does not contain the chart.

## 4. Root Cause Analysis

### RCA-1 — PPTX orchestration drops the chart artifact

The PPTX branch in `src/cognishift/core/engine.py` builds slide dictionaries containing only `title` and `bullet_points`. It never queries the current run's PNG artifact and never attaches an image or chart artifact ID.

Relevant locations:

- `src/cognishift/core/engine.py:3380` — PPTX branch begins
- `src/cognishift/core/engine.py:3406` — text-only slide dictionaries
- `src/cognishift/core/engine.py:3424` — tool parameters omit chart/image references

The tool contract also cannot express an embedded visual:

- `src/cognishift/core/tool_schemas.py:241` — `PptxSlide` contains only `title` and `bullet_points`
- `src/cognishift/core/tools.py:440` — `generate_pptx` constructs a generic custom spec
- `src/cognishift/core/artifact_quality/service.py:670` — generic specs use the legacy renderer
- `src/cognishift/core/artifact_generators.py:376` — legacy PPTX renderer adds only title and bullet slides

### RCA-2 — Duplicate branches make PDF chart attachment unreachable

The engine contains two `target_fmt == "pdf"` branches and two `target_fmt == "both"` branches.

The first branches execute at:

- `src/cognishift/core/engine.py:3353` — first combined DOCX+PDF branch
- `src/cognishift/core/engine.py:3371` — first PDF branch

These first branches do not query or attach the PNG.

Later branches at lines 3465 and 3488 contain the intended chart lookup and attachment logic, but they are unreachable because the earlier branches already match the same conditions.

This explains why:

- PDF-only contains no chart.
- Combined DOCX+PDF produces a DOCX without a chart even though DOCX-only works.

### RCA-3 — Multi-format selection cannot represent all requested formats

Format selection assigns one `target_fmt` value. When both DOCX and PDF are present, `target_fmt` becomes `"both"` before PPTX is considered. Therefore, a request containing PPTX, PDF, and DOCX never reaches the PPTX generation branch.

The artifact contract correctly remembers that PPTX is required, so the run later fails with `pptx_deliverable` missing, but it does not generate the missing format.

### RCA-4 — Completion checks verify separate files, not embedding relationships

`GoalContract.check_satisfaction` checks only whether nonempty files of the requested extensions exist. It does not verify that:

- The PNG is embedded in the requested document.
- The embedded image hash matches the generated PNG.
- The document metadata records the embedded artifact ID.

Relevant location: `src/cognishift/core/engine.py:189`.

This allowed run `#101036` to complete despite a text-only PPTX.

### RCA-5 — Figure quality checks are skipped when visual metadata is omitted

The normal engine branches do not pass `candidate_visual_metadata` to the document tools. In `ArtifactGenerationService`, `has_figures` becomes true only when candidate metadata is supplied. Consequently, the following dimensions are recorded as `NOT_APPLICABLE` even for chart-embedding requests:

- `artifact_context_valid`
- `caption_semantic_valid`
- `figure_readability_valid`

This occurred even for the genuinely embedded DOCX from run `#101038`. It also allowed the no-image DOCX files from `#101039` and `#101040` to be marked enterprise-ready.

### RCA-6 — PDF pagination produces an orphan page

All three tested PDF attempts generated nearly identical 4.9 KB, two-page staging files. Page 2 contained only about 71 text characters and 1% vertical occupancy, triggering the fail-closed page-flow gate.

The quality gate is behaving correctly by rejecting the PDF. The generation/layout logic is producing the invalid pagination.

### RCA-7 — Financial workbook sheet and metric selection are unsafe

The earlier financial Excel test, run `#101035`, failed before document generation.

The sheet selector scored:

- `CAPEX_Modernization`: 92
- `Income_Statement_10Y`: 91

Although the code gives the income statement a generic-financial bonus, it also scores almost every query word of three or more characters without adequate stop-word filtering. Narrative CAPEX rows therefore won by one point.

After selecting `CAPEX_Modernization`:

- `Current Operational Status` became the grouping column.
- `Key Value Delivered` became the supposed metric because its name contains `value` and the query included the word `key`.
- Group-by `sum()` concatenated text descriptions.
- The pipeline attempted to convert `Reduces carbon intensity of HGU reforming furnace` to `float` and failed.

Relevant locations:

- `src/cognishift/core/visualization/selector.py:159` — sheet-scoring fallback
- `src/cognishift/core/visualization/selector.py:549` — broad metric-column candidate matching
- `src/cognishift/core/visualization/selector.py:556` — any-word query match
- `src/cognishift/core/visualization/selector.py:563` — grouping and summation
- `src/cognishift/core/visualization/selector.py:565` — failing float conversion

## 5. Required Remediation

### Priority 0 — Correct document embedding

1. Represent requested outputs as a set/list, not one mutually exclusive `target_fmt` string.
2. Query current-run chart artifacts once after visualization generation.
3. Pass the selected chart artifact ID, caption, purpose, source ID, and expected hash into every requested document generator.
4. Extend the PPTX tool schema to accept `image_artifact_ids` or `chart_artifact_ids` per slide.
5. Build a real `PresentationSpec` and use `PresentationRenderer` for normal PPTX requests.
6. Remove the duplicate/unreachable PDF and combined-format branches.

### Priority 0 — Make success mean embedded

1. Extend the goal contract with an embedding requirement when the prompt says `embed`, `insert`, `include inside`, or equivalent.
2. Inspect the final package before acceptance:
   - PPTX: verify slide relationship and `ppt/media` or native chart relationship.
   - DOCX: verify image relationship and `word/media` entry.
   - PDF: verify an image XObject exists on an expected page.
3. Compare the embedded media SHA-256 with the selected chart artifact SHA-256.
4. Require embedded-artifact provenance metadata in the registered document record.
5. Fail closed if a requested image is missing or substituted.

### Priority 1 — Repair PDF layout

1. Rebalance section spacing and page breaks before rendering.
2. Prevent a short verification/footer fragment from being pushed onto a new page.
3. Add a focused regression test for the 71-character orphan-page case.

### Priority 1 — Repair spreadsheet selection

1. Remove generic stop words before sheet scoring.
2. Prefer explicit financial metric sheets for generic financial-trend requests.
3. Require selected metric columns to be numerically typed or safely coercible before aggregation.
4. Do not treat the substring `value` as sufficient proof that a column is numeric.
5. If the user requests generic financial trends, require an explicit, deterministic default metric set such as Revenue, EBITDA, and PAT rather than using a narrative column.

## 6. Regression Acceptance Matrix

The remediation should not be considered complete until all of the following pass through the live UI:

| Test | Required result |
|---|---|
| PNG only | Exactly one correct chart from the selected source and metric |
| PPTX + PNG | PPTX contains the exact generated chart bytes or a verified native chart linked to the same data |
| PDF + PNG | PDF accepted; chart visibly present; no orphan page |
| DOCX + PNG | DOCX contains the exact chart and remains accepted |
| DOCX + PDF + PNG | Both documents embed the chart; both accepted |
| PPTX + PDF + DOCX + PNG | All four requested deliverables generated; chart embedded in every document |
| Invalid metric | Clear failure; no substituted column or chart |
| Wrong equipment/source | Clear abstention; no misleading output |
| Generic financial workbook | Correct income/financial sheet selected; no narrative column treated as numeric |
| Quality-gate negative | Remove the embedded image from a test package and confirm acceptance fails |

## 7. Final Assessment

The problem is **not universal to every document path**, but it affects most multi-artifact combinations:

- PNG generation: working for the controlled CSV case.
- DOCX-only chart embedding: working and hash-verified.
- PPTX chart embedding: broken.
- PDF chart embedding: broken, plus PDF pagination failure.
- Combined DOCX+PDF embedding: broken because the wrong duplicate branch executes.
- All-formats generation: broken because output selection is mutually exclusive and skips PPTX.
- Quality reporting: insufficient because it can label documents enterprise-ready without verifying requested embedded visuals.

The central design defect is that document generation, chart generation, and acceptance validation are treated as separate file-existence events rather than one provenance-linked embedding contract.
