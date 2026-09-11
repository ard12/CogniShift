# DETAILED TECH STACK
## Comprehensive Architectural Breakdown of Technologies, Libraries, and Runtimes
*Smart India Hackathon 2026 | Team 087 (Den of Devs) | Problem Statement: SIH26117*

---

### 1. Architecture Philosophy
CogniShift is designed around four strict engineering principles:
1. **Zero Public-Cloud Egress:** The application runs locally without external cloud dependencies during operation.
2. **Deterministic Verification:** AI models synthesize code; an isolated sandbox executes the code and verifies mathematical tolerances.
3. **Local Open-Weight Models:** Neural weights run locally on consumer/workstation GPUs without proprietary per-token cloud APIs.
4. **Standard Commercial Hardware:** Runs on a single standard workstation PC (NVIDIA RTX 3060/4080 class) with bounded resource consumption.

---

### 2. Full Layer-by-Layer Technology Matrix

| System Layer | Technology Component | Version / Model | Operational Function |
| :--- | :--- | :--- | :--- |
| **User Interface** | React 19 & TypeScript | v19.0.0 / v5.3 | Ultra-fast single-page web console; zero external CDN dependencies. |
| **UI Styling** | Tailwind CSS & Lucide | v3.4 / v0.3 | Industrial dark-mode operator console optimized for control-room monitors. |
| **Session Auth** | W3C WebCrypto API | Native Browser | Hardware-bound ECDSA P-256 session token generation and signing. |
| **API Gateway** | FastAPI & Uvicorn | v0.115 / v0.34 | High-performance asynchronous REST and Server-Sent Events (SSE) gateway. |
| **Database Engine** | SQLite 3 with WAL Mode | v3.45 / aiosqlite | Zero-maintenance local transaction ledger with WAL concurrency. |
| **Model Serving** | Ollama / vLLM-Compatible | Local Serving | Ollama for current local serving; vLLM-compatible serving architecture for continuous-batched, higher-concurrency deployment. |
| **Primary Reasoning** | Qwen-2.5-Coder-7B | AWQ 4-bit Quant | Natural language understanding, multi-step planning, and ASME Python script synthesis. |
| **Multimodal Vision** | Qwen-2.5-VL-7B | 4-bit Quant | Visual P&ID blueprint analysis, instrument tag extraction, and dial gauge reading. |
| **Text Embeddings** | FastEmbed (bge-small) | v0.4 (ONNX CPU) | Local CPU embeddings with low-latency inference and no GPU requirement (0 MB VRAM). |
| **Vector Store** | ChromaDB (Local) | v0.5.23 | Persistent on-disk vector database indexing technical SOP manuals. |
| **Execution Sandbox** | Docker Engine | v26.0+ (--net=none) | Isolated, ephemeral container executing Python ASME calculations safely. |

---

### 3. Component Deep Dive
#### A. Local AI Model Optimization & Serving
CogniShift uses Ollama for current local serving, designed with a vLLM-compatible architecture for continuous-batched, higher-concurrency deployments. 4-bit quantization reduces memory footprint significantly while preserving reasoning ability. Continuous-batched inference enables concurrent users on a single GPU, with horizontal inference-worker scale-out for larger deployments. Quantized models are selected and scheduled according to available VRAM; bounded concurrency prevents uncontrolled GPU memory exhaustion.

#### B. FastEmbed & ONNX Runtime (CPU Offload)
To preserve GPU VRAM strictly for generative reasoning, document vectorization is offloaded entirely to the CPU. Using FastEmbed with the `BAAI/bge-small-en-v1.5` model compiled for ONNX Runtime, CogniShift generates local CPU embeddings with low-latency inference and no GPU requirement using lightweight CPU SIMD instructions (AVX-512/AVX2). This enables responsive document search while keeping GPU memory clear for language and vision models.

#### C. Isolated Docker Sandbox Container
Security in industrial control systems strictly forbids running arbitrary code on the host operating system. CogniShift executes all generated Python calculations inside a temporary, throw-away Docker container configured with:
- `--net=none`: Complete network isolation (no loopback, no outbound network interfaces).
- `--read-only`: Read-only root filesystem prevents writing persistence scripts.
- `--memory=512m --cpus=1.0`: Strict cgroup resource quotas prevent memory leaks or CPU starvation.
- `timeout 30`: Hard execution deadline terminates any accidental infinite loops.

#### D. Write-Ahead Logging (WAL) SQLite Ledger
The backend database uses SQLite configured in WAL (Write-Ahead Logging) mode with `PRAGMA synchronous = NORMAL`. SQLite WAL supports concurrent reads and improves local transaction resilience; production-scale deployments can migrate to a server-grade database (such as PostgreSQL) as scale demands.

---
*CONFIDENTIAL & SOVEREIGN  |  SOVEREIGN ON-PREMISE SYSTEM — ZERO PUBLIC-CLOUD EGRESS DURING OPERATION*
