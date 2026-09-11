# PROJECT ABSTRACT
## Project CogniShift: Sovereign On-Premise Agentic AI Workbench for Confidential Industrial Work
*Smart India Hackathon 2026 | Team 087 (Den of Devs) | Problem Statement: SIH26117*

---

### 1. Executive Summary
Project CogniShift is an on-premise, sovereign artificial intelligence workbench engineered specifically for confidential and safety-critical industrial operations—such as petroleum refineries, chemical processing plants, and heavy utilities. While commercial cloud AI services offer rapid prototyping, industrial operators are constrained by strict data-handling boundaries. Uploading confidential engineering information to third-party cloud services can conflict with organizational confidentiality, cybersecurity, and data-governance requirements.

CogniShift addresses this operational challenge by deploying local open-weight AI models directly within the plant perimeter. The system operates on local hardware with zero external internet dependencies during active execution. Control-room operators can interact with complex operating manuals in natural language, extract technical parameters from scanned P&IDs and analog dials, execute engineering calculations deterministically within an isolated container sandbox, and enforce human-in-the-loop dual-supervisor authorization before any actionable maintenance permit is synthesized.

> **Core Value Proposition**  
> Local operational sovereignty: confidential plant engineering documents, telemetry, and operating procedures remain strictly within facility boundaries. Calculations are executed deterministically and validated against defined engineering constraints, reducing reliance on unverified model arithmetic.

---

### 2. Industrial Problem & Operational Constraints
Heavy industries and safety-critical manufacturing facilities operate under four fundamental constraints:
- **1. Purdue Level 3/3.5 Network Segmentation:** Industrial control environments isolate operational networks from public corporate WANs to safeguard physical infrastructure. Software must operate locally without persistent external connectivity.
- **2. Protection of Confidential Engineering IP:** Piping and Instrumentation Diagrams (P&IDs), valve schedules, and process yield models constitute highly sensitive trade secrets. Local processing ensures this data is not exposed to external servers.
- **3. Requirement of Deterministic Engineering Accuracy:** Generative language models can introduce hallucinations or numerical inaccuracies when performing mental arithmetic. In safety-critical systems, calculations must be synthesized into code and executed within controlled sandboxes against defined constraints.
- **4. Statutory Governance & Auditability:** DPDP and industrial governance requirements motivate strong controls around sensitive data processing, access, and auditability across all engineering operations.

---

### 3. System Architecture & Core Capabilities
CogniShift establishes a modular, five-tier sovereign architecture balancing agentic assistance with deterministic safety gates:

| Functional Tier | Technology Used | Operational Role in Plant |
| :--- | :--- | :--- |
| **1. Visual Blueprint Ingestion** | Qwen-2.5-VL-7B & Classical OCR | Extracts instrument tag numbers from blueprints and reads pointer angles on analog dial gauges. |
| **2. Grounded Technical Retrieval** | ChromaDB & FastEmbed (CPU) | Indexes 500+ page SOP manuals with calibrated similarity thresholds to improve evidence grounding and reduce unsupported responses. |
| **3. Sandboxed Formula Execution** | Docker Container (--net=none) | Executes calculations deterministically and validates them against defined engineering constraints (e.g. ASME Section VIII). |
| **4. Four-Eyes Approval Gate** | ECDSA Cryptographic Sign-Off | Enforces human dual authorization; halts high-consequence execution until two independent supervisors approve. |
| **5. Auditable Local Ledger** | SQLite WAL & Local Mailer | Auditable local ledger with integrity controls and traceable approval history suitable for review and investigation. |

---

### 4. Deployment Feasibility & Hardware Footprint
CogniShift is engineered to operate on standard commercial edge workstation hardware:
- **Processor:** Standard 8-core CPU (e.g., Intel Core i7 12th Gen or AMD Ryzen 7).
- **Memory:** 16 GB to 32 GB of system RAM.
- **Graphics Card:** Single 12 GB-class GPU (e.g., NVIDIA RTX 3060 12GB or RTX 4080 16GB) under configured quantization/resource limits.
- **Scalability & Concurrency:** Continuous-batched inference enables concurrent users on a single GPU, with horizontal inference-worker scale-out for larger deployments.
- **Operating System:** Standard 64-bit Linux (Ubuntu / Rocky Linux) or Windows 10/11 Enterprise.
- **Network Footprint:** Zero public-cloud egress during operation. Operates over the local plant LAN (Purdue Level 3).

---

### 5. Conclusion
Project CogniShift demonstrates that high-hazard industrial environments can safely adopt generative and agentic AI without compromising confidentiality, sovereignty, or regulatory alignment. By combining local open-weight models, deterministic calculation verification, and cryptographic human authorization, CogniShift provides a solution that is practical and deployment-oriented for controlled on-premise industrial environments.

---
*CONFIDENTIAL & SOVEREIGN  |  SOVEREIGN ON-PREMISE SYSTEM — ZERO PUBLIC-CLOUD EGRESS DURING OPERATION*
