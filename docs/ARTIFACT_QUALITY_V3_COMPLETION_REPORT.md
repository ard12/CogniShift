# CogniShift Artifact Quality V3 — Completion and Handoff Report

**Report date:** 2026-09-14  
**Repository:** `C:\Users\sitan\OneDrive\Desktop\CogniShift`  
**Branch:** `main`  
**Starting HEAD:** `82156997fd9b8b9ad1b02aa8bc5d09708d811251`  
**Overall status:** Scoped Artifact Quality V3 demo-blocker work completed and verified. One environment-dependent PowerPoint COM test remains unresolved.

## 1. Executive Summary

The Artifact Quality V3 screening workflow was repaired and stabilized. The canonical management presentation now embeds the grounded Plant P&ID on Slide 5 and the telemetry chart on Slide 6. The presentation, technical PDF, and emergency-procedure DOCX are generated through the production artifact service and pass the repository's quality gates.

The visual QA workflow was corrected to require and account for all **15 rendered surfaces**:

- 10 PowerPoint slides
- 2 PDF pages
- 3 DOCX pages

All 15 surfaces were rendered and manually inspected. No blank pages, broken images, clipping, or overlapping content were found. Exact sovereignty wording is visible in all three canonical deliverables.

The VLM performance problem was also investigated. FastEmbed was attempting to initialize CUDA and consuming GPU resources needed by the vision model. FastEmbed is now explicitly assigned to the CPU, allowing the Qwen vision model to use the GPU substantially more effectively.

No commit or push was performed. Pre-existing working-tree changes were preserved.

## 2. Requested Scope Completed

### Grounded presentation visuals

- Slide 5 uses the existing, source-grounded Plant P&ID image when available.
- Slide 5 retains a text fallback when no grounded topology image is supplied.
- Slide 6 embeds the canonical telemetry chart.
- Tests verify the actual PPTX image relationships and the hashes of the embedded media.

### Production artifact generation

- PPTX, PDF, and DOCX outputs are generated through `ArtifactGenerationService`.
- Canonical source images are registered with semantic metadata and provenance.
- The production workflow builds grounded artifact context before presentation planning.
- Artifact quality failures are fail-closed and include explicit diagnostics instead of silently remaining in a staging state.

### Visual QA accounting

- Expected visual count corrected to 15.
- QA now fails if expected render surfaces are missing.
- A canonical visual QA report is written with expected, discovered, reviewed, and missing counts.
- All 15 final surfaces were manually reviewed.

### Sovereignty language

The following exact sentence is now used consistently and rendered visibly in the canonical PPTX, PDF, and DOCX:

> Local sovereign execution with no public-cloud AI/model dependency in the demonstrated workflow.

### VLM GPU utilization

- FastEmbed `TextEmbedding` is explicitly configured with `providers=["CPUExecutionProvider"]`.
- This prevents the embedding runtime from unsuccessfully initializing CUDA because of the missing `cudnn64_9.dll` dependency and from fragmenting or occupying GPU resources required by the VLM.
- After the change, `qwen2-vl:2b` reported 100% GPU utilization during the tested P&ID workflow.
- `qwen2-vl:7b` reported approximately 58% GPU / 42% CPU during the deeper test.

## 3. Implementation Details

| Area | File | Work performed |
|---|---|---|
| Presentation planning | `src/cognishift/core/presentation/planner.py` | Added `topology_image_artifact_ids`; Slide 5 selects an image-with-explanation layout when a grounded topology visual exists, with text fallback retained. |
| Screening workflow | `scripts/run_screening_demo_workflow.py` | Registers the telemetry chart and existing rendered Plant P&ID with provenance; supplies them to Slides 5 and 6; generates all canonical artifacts through the production service; enforces 15-surface fail-closed QA; writes the visual QA report. |
| Quality lifecycle | `src/cognishift/core/artifact_quality/service.py` | Added real caption semantic checks using visible slide content; validates registered source-image readability; prevents absent checks from leaving artifacts silently in `STAGING`; forwards the sovereignty statement to PDF rendering. |
| Presentation rendering | `src/cognishift/core/presentation/renderer.py` | Increased disclosure, footer, slide-number, metric-subtext, evidence, and chart body typography to meet readability requirements. |
| PDF generation | `src/cognishift/core/artifact_generators.py` | Renders the exact sovereignty statement visibly instead of retaining it only as planner metadata. |
| Embedding runtime | `src/cognishift/core/retriever.py` | Pins FastEmbed to `CPUExecutionProvider` so the VLM can use the GPU without competing ONNX CUDA initialization. |
| Wording consistency | Multiple planners, validators, tools, benchmark scripts, and tests | Replaced earlier wording with the exact approved sovereignty sentence. |
| Provenance tests | `tests/test_pptx_generation_and_provenance.py` | Corrected monkeypatch signature and added production verification of Slide 5/6 image relationships and embedded media hashes. |
| Semantic tests | `tests/test_artifact_quality_v3_semantic_failures.py` | Updated expected sovereignty wording. |
| Backlog | `docs/POST_SELECTION_ARTIFACT_BACKLOG.md` | Froze V3 for screening and retained only non-critical pagination/page-density and polish items. |

The exact sovereignty wording was also updated in:

- `src/cognishift/core/artifact_quality/schemas.py`
- `src/cognishift/core/report_planner.py`
- `src/cognishift/core/sop_planner.py`
- `src/cognishift/core/repair_service.py`
- `src/cognishift/core/compatibility_validator.py`
- `src/cognishift/core/tools.py`
- `scripts/run_rca_e2e_benchmark_v4.py`
- `scripts/run_rca_e2e_benchmark_v4_1.py`
- `scripts/run_rca_e2e_benchmark_v4_2.py`
- `tests/test_truth_chain_v4_2.py`

## 4. Canonical Output Inventory

Output directory:

`C:\Users\sitan\OneDrive\Desktop\CogniShift\data\screening_smoke_artifacts`

| Artifact | Latest DB artifact ID | Quality report | Result | SHA-256 |
|---|---:|---|---|---|
| `Management_RCA_Brief.pptx` | 1041 | `QREP-90700DA77DFE` | Demo ready; enterprise ready | `9B14D6843739D67F0289C86CA19F781416121253BC1EFC9E501C6EAB196EBA4C` |
| `Technical_Investigation.pdf` | 1042 | `QREP-091537330D18` | Demo ready; enterprise ready | `F3CA88C9D9077DB437339640E1CDB491E60EF77C7AC5279F83683649357FB2AE` |
| `Emergency_Procedure.docx` | 1040 | `QREP-E3401C4DF1D9` | Demo ready; enterprise ready | `DEBFBE876FDBA1A50E39BD85A316868C434B5B16767AF913746B2EA55F7CE708` |

### PPTX-specific evidence

- 10 slides generated.
- Independent typography validation: `typography_valid: true` and zero role-based font violations.
- Slide 5 contains a picture relationship to `../media/image1.png`.
- Slide 5 media SHA-256: `F01B6000202056FD7441672C26874F4A029D6ED79AEFB60B6DC6097870B226F0`.
- That hash matches the grounded Plant P&ID page image.
- Slide 6 contains a picture relationship to `../media/image2.png`.
- Slide 6 media SHA-256: `00412DA5A896CAE441AAAABC6A66CC1794EEF1F475FBFBEBA9494684EC50EFD5`.
- That hash matches the canonical telemetry chart.

### Round-trip retrieval evidence

- The generated presentation was re-ingested successfully.
- Round-trip source ID: `888888`.
- All 10 slides were indexed.
- A verification query retrieved Slide 7 exactly.
- Citation produced: `[Management_RCA_Brief.pptx | Slide 7 | TEXT]`.

## 5. Verification Results

### Production workflow

The complete screening workflow finished successfully in approximately **1,880 seconds** and reported:

```text
Canonical visual QA: 15/15 surfaces, 0 missing
Round-trip: SUCCESS
```

### Visual inspection

The following render surfaces were reviewed individually:

- `rendered_slides/slide_1.png` through `rendered_slides/slide_10.png`
- `canonical_previews/pdf_page_1.png` and `pdf_page_2.png`
- `canonical_previews/docx_page_1.png` through `docx_page_3.png`

Result: **15 expected, 15 discovered, 15 reviewed, 0 missing**.

No clipping, overlap, broken images, or blank surfaces were observed. PDF page 2 and DOCX page 2 are intentionally sparse but valid; page-density refinement remains a non-critical backlog item.

### Automated tests

Focused suite:

```text
pytest tests/test_pptx_generation_and_provenance.py tests/test_artifact_quality_v3_semantic_failures.py -q
17 passed in 4.76s
```

Expanded suite:

```text
pytest tests/test_pptx_generation_and_provenance.py tests/test_artifact_quality_v3_semantic_failures.py tests/test_universal_artifact_pipeline_generalization.py -q
29 passed, 1 failed in 166.91s
```

The single failing test was retried independently and failed again:

```text
tests/test_universal_artifact_pipeline_generalization.py::test_pptx_02_boiler_drum_level_excursion
```

This failure is described in Section 7.

Additional checks:

- Python compilation checks passed for the modified key modules and workflow script.
- `git diff --check` passed after two trailing spaces were removed; only Windows CRLF conversion warnings remained.
- The exact sovereignty sentence was confirmed by text extraction from all three final artifacts.

## 6. Generated Evidence Files

The canonical output directory contains the following handoff evidence:

- `canonical_visual_qa_report.json` — 15/15 visual accounting with zero missing surfaces.
- `pptx_validation_report.json` — demo ready, typography valid, zero font violations.
- `round_trip_reingestion_report.json` — successful re-ingestion and retrieval of Slide 7.
- `screening_demo_workflow_report.json` — final workflow summary.
- `rendered_slides/` — rendered PowerPoint slides.
- `canonical_previews/` — rendered PDF and DOCX pages.

## 7. Remaining Known Issue

One expanded-suite case remains unresolved because Microsoft PowerPoint's COM automation host disconnects while rendering:

```text
0x80010108 — The object invoked has disconnected from its clients
```

Impact:

- The affected generated test presentation cannot complete the render-dependent quality gate in that run, so its quality report is not marked demo-ready or enterprise-ready.
- This is isolated to the PowerPoint COM rendering host used by the test.
- The three canonical screening artifacts rendered successfully multiple times and are not blocked by this failure.

Attempted mitigation:

- PowerPoint `DispatchEx` isolation was tested.
- It did not resolve the host disconnect and was reverted to avoid introducing an unverified behavior change.

Recommended follow-up:

- Run presentation rendering in a dedicated disposable worker process with bounded retries and explicit PowerPoint process cleanup.
- Add a renderer-health preflight before large or repeated COM render batches.
- Keep this work separate from the frozen Artifact Quality V3 content patch.

## 8. Non-Critical Backlog

- Improve page density/pagination for sparse PDF and DOCX pages.
- Apply optional visual polish after screening.
- No synthetic P&ID generation work is required for this release because the existing grounded Plant P&ID was successfully used.

## 9. Reproduction and Handoff Checklist

Another agent can verify the completed work as follows:

1. Preserve the current dirty worktree; do not reset unrelated user changes.
2. Run the focused tests listed in Section 5.
3. Run `scripts/run_screening_demo_workflow.py` using the repository's configured Python environment.
4. Confirm that `canonical_visual_qa_report.json` reports 15 expected, 15 discovered, 15 reviewed, and 0 missing.
5. Confirm that all three canonical quality reports are demo-ready and enterprise-ready.
6. Open Slide 5 and verify the grounded P&ID is visible.
7. Open Slide 6 and verify the telemetry chart is visible.
8. Extract text from the PPTX, PDF, and DOCX and verify the exact sovereignty sentence.
9. Run the round-trip retrieval check and confirm that Slide 7 is retrieved with its presentation citation.
10. Treat the isolated PowerPoint COM disconnect as the remaining environment-level stabilization item.

## 10. Repository State

- No commit was created.
- No changes were pushed.
- Existing unrelated modifications were left intact.
- `scripts/run_screening_demo_workflow.py` was already untracked before this work and remains part of the working-tree handoff.
- Artifact Quality V3 is frozen for the screening workflow, subject only to the explicit remaining COM-renderer issue and non-critical backlog above.
