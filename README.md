# CogniShift: Sovereign On-Premise Agentic AI Workbench for Industrial Operations

[![SIH26117](https://img.shields.io/badge/SIH%20Problem-SIH26117-orange.svg)](https://www.sih.gov.in/)
[![Industrial Context](https://img.shields.io/badge/Industrial%20Partner-MRPL%20Refinery-blue.svg)](https://www.mrpl.co.in/)
[![Python](https://img.shields.io/badge/Python-3.12-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-teal.svg)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/Frontend-React%2019%20%7C%20Vite%20%7C%20Tailwind%20v4-blueviolet.svg)](frontend/)
[![Local LLM](https://img.shields.io/badge/Local%20LLM-Qwen%202.5%207B%20%7C%20Llama%203.2%203B-purple.svg)](https://ollama.com/)
[![Local Vision](https://img.shields.io/badge/Local%20VLM-Moondream%201.86B-darkred.svg)](https://ollama.com/)
[![Local Embeddings](https://img.shields.io/badge/Embeddings-FastEmbed%20CPU%20ONNX-blue.svg)](https://github.com/qdrant/fastembed)
[![Vector Store](https://img.shields.io/badge/Vector%20Store-ChromaDB%20(Local)-lightgrey.svg)](https://www.trychroma.com/)
[![Database](https://img.shields.io/badge/Database-Async%20SQLite%20(WAL%20Mode)-003B57.svg)](https://sqlite.org/)
[![Tests](https://img.shields.io/badge/Tests-554%20Passing-brightgreen.svg)](tests/)

**CogniShift** is an on-premise agentic AI workbench designed for critical process plants, refineries, and air-gapped industrial infrastructure. Built for Smart India Hackathon problem statement **SIH26117** in collaboration with **Mangalore Refinery and Petrochemicals Limited (MRPL)**, CogniShift operates entirely within a plant's local perimeter without external cloud network dependencies.

All language models, visual language models, embedding pipelines, and vector indexes execute locally. Physical equipment actions are protected by deterministic human-in-the-loop authorization gates, and multi-terminal access across the plant LAN is governed by browser-generated cryptographic device enrollment.

---

## Key Capabilities

* **On-Premise Model Runtimes:** Executes open-weight models (Qwen 2.5 7B, Llama 3.2 3B, Moondream 1.86B) via local Ollama / vLLM backends. No outbound API calls are made to external providers.
* **Calibrated Page-Aware Retrieval:** Ingests engineering manuals, P&IDs, and SOPs with strict 1-based page boundary preservation using CPU-based FastEmbed ONNX embeddings and ChromaDB. Citations are reconciled against retrieved chunks to ensure verifiable evidence attribution.
* **Deterministic Four-Eyes Safety Gates:** High-consequence industrial actions (e.g. emergency relief valve operation, pump shutdown) cannot be triggered directly by model output. The state machine pauses and requires dual supervisor authorization before executing actuator tools.
* **Verifiable Deliverable Generation:** Executes engineering calculations deterministically in isolated code sandboxes and synthesizes formal deliverables (Excel workbooks, Word memos, publication-grade PDFs, and telemetry charts) verified by SHA-256 integrity checksums.
* **Hardware-Bound Device Security:** Terminal identities on the control room LAN are anchored to non-exportable WebCrypto ECDSA P-256 keys. API calls require cryptographic challenge-response validation, mitigating session hijacking and unauthorized LAN access.
* **Air-Gapped Sovereign Mailbox:** An internal loopback SMTP server (port 1025) enables operators and supervisors to exchange formal shift handovers and safety alerts with grounded manual citations and attachment verification.

---

## High-Level Architecture

`
+-------------------------------------------------------------------------------+
|                    PLANT LAN & OPERATOR INTERFACES                            |
|  Control Room Workstation  -  Field Tablet  -  Supervisor Terminal (HTTPS)    |
+---------------------------------------+---------------------------------------+
                                        |  (WebCrypto ECDSA Device Auth)
                                        v
+-------------------------------------------------------------------------------+
|                        COGNISHIFT BACKEND (FASTAPI)                           |
|                                                                               |
|  1. Semantic Intent Router (7 Intent Classes + Cosine Distance Margin)        |
|  2. Multi-Turn State Machine (CAS Atomic Resumption, 15-min TTL, Context)    |
|  3. Knowledge Substrate (ChromaDB + FastEmbed ONNX + Exact Citations)         |
|  4. Plant Topology Graph (Equipment Feeds, Protection Valves, Sensors)        |
|  5. Human-in-the-Loop Gate (Dual Supervisor Signature for Physical Tools)     |
|  6. Deliverable Pipeline (Excel, Word, PDF, Charts with SHA-256 Integrity)   |
+---------------------------------------+---------------------------------------+
                                        |
        +-------------------------------+-------------------------------+
        |                               |                               |
        v                               v                               v
+----------------+              +----------------+              +----------------+
|  LOCAL OLLAMA  |              | DOCKER SANDBOX |              | LOCAL STORAGE  |
|  Qwen 2.5 7B   |              | Python Runner  |              | SQLite (WAL)   |
|  Llama 3.2 3B  |              | Zero Net Egress|              | ChromaDB Store |
|  Moondream VLM |              | Resource Bound |              | Artifact Vault |
+----------------+              +----------------+              +----------------+
`

---

## System Workflow

1. **Intent Classification:** The FastEmbed semantic router classifies incoming queries into one of 7 discrete intents (CONVERSATION, KNOWLEDGE_QUERY, ARTIFACT_INSPECTION, CODE_EXECUTION, CONTROL_ACTION, UI_NAVIGATION, COMPLEX_AGENT) with calibrated cosine distance thresholds.
2. **Context Assembly:** Relevant chunks from authorized documents and plant topology graph neighbors are assembled into structured context tags.
3. **Reasoning & Tool Proposal:** The local LLM plans steps and proposes tool calls conforming to strict Pydantic schemas.
4. **Safety Interlock Evaluation:** Read-only tools execute immediately; high-risk tools halt the run, issue an pproval_request, and notify supervisors via the internal air-gapped mail system.
5. **Synthesis & Evidence Reconciliation:** The final response is cross-referenced against retrieved evidence chunks. Document citations are standardized into [<Document> | Page <X> | <METHOD>] format, and sources_used is recorded with exact provenance.
6. **Deliverable Production:** If requested, structured data is rendered into Excel, Word, or PDF artifacts with cryptographic integrity hashes recorded in the audit log.

---

## Installation & Setup

### Prerequisites
* **Operating System:** Windows 10/11, Ubuntu 22.04+, or Debian 12 (Offline / Air-gapped supported)
* **Python:** 3.12+ (64-bit)
* **Node.js:** 20+ and npm 10+ (for the React 19 web console)
* **Ollama:** Local inference engine with downloaded models:
  `ash
  ollama pull qwen2.5:7b
  ollama pull llama3.2:3b
  ollama pull moondream
  `

### 1. Clone & Configure Virtual Environment
`ash
git clone https://github.com/your-org/CogniShift.git
cd CogniShift

python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux:
source .venv/bin/activate

pip install -r requirements.txt
`

### 2. Environment Configuration
Copy the example environment template:
`ash
cp .env.example .env
`
Default configuration runs in sovereign offline mode:
* OPERATING_MODE=local
* FASTEMBED_OFFLINE=true
* OLLAMA_BASE_URL=http://localhost:11434
* CHROMA_PATH=./data/chroma
* SQLITE_PATH=./data/cognishift.db

### 3. Start the Services

**Backend API:**
`ash
uvicorn cognishift.app.main:app --host 127.0.0.1 --port 8000
`

**Frontend Operator Console:**
`ash
cd frontend
npm install
npm run dev
`
Open http://localhost:5173 in a modern browser. The application will guide you through local device enrollment.

---

## Core API Endpoints

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| POST | /api/v1/workspaces | Create and manage isolated multi-tenant workspaces |
| GET | /api/v1/agents | List authorized agent profiles and permitted tool bindings |
| POST | /api/v1/knowledge/upload | Ingest engineering manuals with page-aware chunking |
| GET | /api/v1/knowledge | List indexed knowledge sources and vector counts |
| POST | /api/v1/runs | Execute an agent reasoning run or operational query |
| GET | /api/v1/runs/{id} | Retrieve run status, execution timeline, and verified citations |
| GET | /api/v1/approvals | List pending high-risk tool authorization requests |
| POST | /api/v1/approvals/{id}/approve | Sign off on a tool action (supervisor dual-signature) |
| GET | /api/v1/artifacts | List and download generated deliverables (Excel, PDF, Word) |
| GET | /api/v1/mail/inbox | Access internal air-gapped shift handovers and safety alerts |
| POST | /api/v1/authorizations/device/register| Register trusted terminal WebCrypto public key |

---

## Verification & Automated Test Suite

CogniShift includes a comprehensive test suite validating safety gates, citation grounding, concurrency, and security policies:

`ash
# Run all unit and integration tests:
pytest tests/ -v

# Run citation accuracy and grounding tests:
pytest tests/test_single_provenance_and_grounding.py -v

# Run safety interlock and tool approval tests:
pytest tests/test_phase2a_tool_calling.py tests/test_phase2b_agent_loop.py -v

# Run network sovereignty and isolation tests:
pytest tests/test_phase0_security.py tests/test_phase6_browser_egress.py -v
`

---

## Repository Structure

`
CogniShift/
├── config/                 # Network policies and system configuration
├── data/                   # Local SQLite DB and ChromaDB vector store
├── demo/                   # Synthetic refinery manuals, telemetry datasets, and P&IDs
├── docs/                   # System design, workflow documentation, and presentation PDFs
│   ├── CogniShift_SIH2026_Final_v2.pdf
│   ├── DETAILED_PROJECT_WORKFLOW.md
│   ├── DETAILED_TECH_STACK.md
│   ├── PROJECT_ABSTRACT.md
│   └── RESEARCH_AND_REFERENCES.md
├── frontend/               # React 19 + Vite + Tailwind v4 operator console
│   ├── src/                # Pages, components, API client, WebCrypto identity
│   └── package.json
├── scripts/                # Administration, demo seeding, and LAN TLS scripts
├── src/cognishift/         # Core application package
│   ├── app/                # FastAPI application, routers, models, database
│   │   ├── api/            # Route controllers (runs, knowledge, approvals, mail)
│   │   └── db/             # Async SQLite schema, connection lifecycle, models
│   └── core/               # Agentic engine, retriever, tools, sandbox, vision
│       ├── engine.py       # Multi-step execution loop and citation reconciliation
│       ├── retriever.py    # ChromaDB search and metadata filtering
│       ├── tools.py        # Industrial tool definitions and simulated actuators
│       ├── semantic_router.py # 7-intent FastEmbed classifier
│       └── document_processing/ # Multimodal PDF extractor, OCR, provenance
├── tests/                  # 550+ automated unit, regression, and security tests
├── requirements.txt        # Python dependency manifest
└── pytest.ini              # Test runner configuration
`

---

## Compliance & Standards Alignment

* **IEC 62443 (Industrial Cybersecurity):** Operates entirely within Purdue Model Level 3/3.5 manufacturing operations DMZ with fail-closed network policies and verified local device enrollment.
* **OSHA 1910.119 (Process Safety Management):** Enforces strict Four-Eyes dual-supervisor sign-off on operating envelope excursions and emergency shut-off controls.
* **DPDP Act 2023 (Data Sovereignty):** Prevents external data residency violations by processing and storing all operational logs, telemetry, and documents exclusively on local plant hardware.
