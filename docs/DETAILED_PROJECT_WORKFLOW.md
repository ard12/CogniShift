# DETAILED PROJECT WORKFLOW
## Eight-Stage Operational Lifecycle for Governed Industrial AI Workflows
*Smart India Hackathon 2026 | Team 087 (Den of Devs) | Problem Statement: SIH26117*

---

### 1. The 8-Stage Closed-Loop Operational Cycle
Project CogniShift structures plant workflows into a closed-loop, eight-stage operational cycle:  
**CAPTURE $\rightarrow$ PROCESS $\rightarrow$ ANALYZE $\rightarrow$ ALERT $\rightarrow$ VERIFY $\rightarrow$ ACT $\rightarrow$ LEARN $\rightarrow$ IMPROVE**

This structured pipeline ensures that every relevant engineering calculation is executed and validated through a controlled sandbox workflow, and authorized by human shift supervisors before any equipment permit is released.

> **Sovereignty & Safety Rule**  
> At no point in this workflow does the AI have direct physical actuation capability. The system transitions strictly between deterministic, auditable states, concluding in cryptographic dual-supervisor sign-off.

---

### 2. Detailed Breakdown of Operational Stages

#### Stage 1: CAPTURE — Air-Gapped Ingestion & Multi-Source Data Ingestion
- **Blueprints & Schematics:** Ingests scanned Piping & Instrumentation Diagrams (P&IDs) and electrical single-line drawings without cloud processing.
- **Analog Gauge Feeds:** Captures images of Bourdon tube pressure dials and level indicators directly from local maintenance cameras or operator tablets.
- **Engineering Manuals:** Accepts 500+ page PDF operating manuals, ASME standard codes, and manufacturer equipment rating plates.
- **Network Footprint:** Zero public-cloud egress during operation; all ingestion operates locally within the plant network perimeter.

#### Stage 2: PROCESS — Local OCR Extraction & Spatial Vectorization
- **Optical Character Recognition:** RapidOCR extracts text, line tags, and instrument bubble codes (e.g., 'PT-101', 'V-102') locally on CPU.
- **Dial Gauge Trigonometry:** Calculates needle pointer angles against calibrated minimum and maximum dial markings to infer physical pressures.
- **CPU Vector Embeddings:** FastEmbed generates local CPU embeddings with low-latency inference and no GPU requirement.
- **Local ChromaDB Indexing:** Stores chunk vectors alongside page numbers, file hashes, and equipment tags in local on-disk storage.

#### Stage 3: ANALYZE — 7-Intent Semantic Routing & Grounded Context Retrieval
- **Intent Classification:** A fast cosine router classifies operator requests into 7 discrete intents (e.g., Blueprint Query, Code Execution, Control Action).
- **Ambiguity Detection:** If an operator query is ambiguous or out of scope, the system halts immediately and asks for clarification.
- **Configured Retrieval Threshold:** Uses a configured retrieval threshold to filter weak evidence and abstain when sufficient support is unavailable.
- **Multi-Step Reasoning:** Qwen-2.5-Coder-7B synthesizes an execution plan referencing exact manual citations (e.g., [Manual | Page 42]).

#### Stage 4: ALERT — Threshold Detection & Out-of-Bounds Warning
- **Operating Limit Check:** Compares inferred or calculated pressures against Maximum Allowable Working Pressure (MAWP) defined in plant specs.
- **Visual Console Warnings:** Displays high-contrast alert badges in the operator console if a reading indicates potential equipment overpressure.
- **Air-Gapped Loopback Mailer:** Dispatches instantaneous email alerts to shift supervisor inboxes via a local Python SMTP service (port 1025).
- **Pre-Execution Hold:** Prevents operators from proceeding until safety warnings are formally acknowledged.

#### Stage 5: VERIFY — Sandboxed ASME Math & Self-Healing Retry Loop
- **Deterministic Code Generation:** The model does NOT guess calculations; it writes a self-contained Python script implementing exact ASME formulas.
- **Isolated Docker Execution:** The script runs inside a secured container with no network access (`--net=none`), read-only root, and 512MB RAM limit.
- **Tolerance Validation:** Calculated pressure drop and wall thickness values are checked against material yield strengths and design margins.
- **Automated Math Retry Loop:** If a script produces a traceback or syntax error, the system self-heals by analyzing stderr and re-synthesizing the code.

#### Stage 6: ACT — The Four-Eyes Principle (Human-in-the-Loop Safety Gate)
- **Autonomous Actuation Prohibited:** The AI is physically incapable of turning valves or tripping pumps directly.
- **Dual Supervisor Permitting:** High-consequence actions generate a formal work permit requiring sign-off from TWO independent shift supervisors.
- **Cryptographic ECDSA Signatures:** Supervisors sign the authorization using hardware-bound cryptographic keys (W3C WebCrypto P-256).
- **Controlled Release:** Only after both signatures match does the system output the verified permit for execution.

#### Stage 7: LEARN — Local Context Retention & Session Continuity
- **Shift Handover Context:** Maintains multi-turn context across consecutive operational shifts in a local SQLite session cache.
- **Operator Feedback Capture:** Logs operator corrections and verified parameters into local memory without altering base model weights.
- **Replay Resistance:** Applies a 15-minute time-to-live (TTL) and atomic nonces to ensure authorization requests cannot be replayed.
- **Zero Cloud Leaks:** Context retention is confined to the local workstation; zero data is transmitted to foundation model vendors.

#### Stage 8: IMPROVE — Verified Deliverables & Integrity-Checked Audit Logging
- **Executive Deliverables:** Generates formatted .docx summary reports, live .xlsx calculation sheets with active formulas, and SHA-256 signed PDFs.
- **Integrity-Checked Audit Ledger:** Every user prompt, retrieved citation, synthesized script, and supervisor signature is logged in an append-only SQLite WAL table.
- **Traceable Audit History:** Provides a traceable audit history suitable for review and investigation under industrial safety guidelines.
- **Historical Analysis:** Supports faster recurring maintenance analysis by preserving verified historical context.

---
*CONFIDENTIAL & SOVEREIGN  |  SOVEREIGN ON-PREMISE SYSTEM — ZERO PUBLIC-CLOUD EGRESS DURING OPERATION*
