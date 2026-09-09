# CogniShift Comprehensive Workflow Validation Report

**Validation date:** 2026-09-04  
**Environment:** Windows workstation, local FastAPI, SQLite, ChromaDB/FastEmbed, Ollama, RapidOCR, Moondream, Docker Desktop  
**Scope:** Backend, CLI, browser workflows, authentication/RBAC, agent execution, OCR/vision, RAG/provenance, artifact generation, approvals, sandboxing, and sovereignty controls  
**Overall result:** 226 automated checks passed, 0 failed, 0 skipped. Live browser and real-runtime gates also passed, with the observations documented below.

## 1. Executive Outcome

CogniShift is operational as a local-first industrial AI workbench. Authentication, workspace isolation, local inference, tool calling, document processing, OCR, vision, provenance, approval controls, artifact handling, Docker isolation, audit logging, and network policy enforcement were exercised. The activity console now also works as a conversational control surface and can navigate the application without requiring the sidebar.

Two defects found during this audit were fixed:

1. Pytest was writing regression fixtures into the real demo SQLite and Chroma stores. Tests now create and remove a disposable runtime tree before CogniShift modules load.
2. A live approval could return HTTP 500 because `sqlite3.Row` was treated as an object supporting `.get()`. The handler now converts the row to a dictionary, and a real SQLite two-stage approval regression test was added.

The pushable backend/documentation regression baseline is **219 tests**. Seven frontend-only UI checks are intentionally retained locally, making the complete local working-tree result **226 tests**.

## 2. Detailed Feature Matrix

| Area | Feature or workflow tested | Method | Outcome |
|---|---|---|---|
| Startup | FastAPI application startup and database initialization | Automated and live server | PASS |
| Startup | Offline readiness checker | CLI/live dependency inspection | PASS |
| Authentication | Unauthenticated API rejection | API tests | PASS |
| Authentication | Invalid and revoked bearer rejection | API tests | PASS |
| Authentication | Operator, supervisor, and administrator bearer identities | API tests | PASS |
| Authentication | Loopback-only ephemeral demo sessions | API and browser | PASS |
| Authentication | Demo identity response does not expose passwords, tokens, keys, or secrets | Security tests | PASS |
| Authentication | Sam operator login | Fresh browser session | PASS |
| Authentication | Jane supervisor session | Live local API | PASS |
| Authentication | Rohit administrator login/session | Browser and live local API | PASS |
| Authentication | Session token storage and purge behavior | Static/security tests and fresh-session behavior | PASS |
| RBAC | Workspace allow-list enforcement | API and knowledge-boundary tests | PASS |
| RBAC | Operator cannot approve own high-risk request | API test | PASS |
| RBAC | Approver must differ from requester | API tests | PASS |
| RBAC | Stage 2 approver must differ from Stage 1 | API tests | PASS |
| Approvals | Single-stage approval/rejection | API tests | PASS |
| Approvals | Dual Four-Eyes Stage 1 and Stage 2 | Automated and live API using Jane then Rohit | PASS |
| Approvals | SQLite-row live handler regression | New real-database test | PASS |
| Approvals | Resume a paused run after authorization | Automated and live API | PASS; live completion took about 97 seconds |
| Approvals | Reject request and preserve safe state | Browser/API | PASS |
| Workspaces | Create, list, fetch, and isolate workspaces | Database/API tests and browser | PASS |
| Agents | Create/list agent definitions and enforce workspace ownership | API/CLI/browser | PASS |
| Routing | Task classification and model-provider abstraction | Router/provider tests | PASS |
| Routing | Local Ollama text model availability (`llama3.2:3b`) | CLI status and live workflow | PASS |
| Routing | Local vision model availability (`moondream`) | CLI status and real vision tests | PASS |
| Agent loop | Multi-step planning, observation, retry, completion, and failure paths | Agent-loop/adversarial tests | PASS |
| Tool calling | Structured tool-call parsing and schema validation | Automated tests | PASS |
| Tool calling | Unknown, malformed, and timed-out model responses fail closed | Adversarial tests | PASS |
| Plant tools | Sensor/telemetry inspection | Live `analyze p101a` command | PASS; returned 105.2 PSI nominal assessment |
| Plant tools | Maintenance and operational action schemas | Automated tests | PASS |
| Database | SQLite WAL schema, CRUD, migrations, and persistence | Database tests | PASS |
| Knowledge | Native PDF extraction | Automated document tests | PASS |
| Knowledge | Scanned PDF/image OCR through RapidOCR | Real OCR suite and uploaded inspection report | PASS |
| Knowledge | Image understanding through Moondream | Real vision suite | PASS |
| Knowledge | Mixed native/OCR page processing | Document tests | PASS |
| Knowledge | Local embeddings and Chroma indexing | Knowledge tests and CLI status | PASS |
| Knowledge | Workspace-isolated retrieval | Boundary tests | PASS |
| Knowledge | Prompt-injection and source-boundary defenses | Adversarial tests | PASS |
| Provenance | Page-level text, extraction method, and confidence | API/browser | PASS |
| Provenance | `P-101A_Inspection_Report.pdf` source trace | Browser modal | PASS; Page 1 displayed critical readings and recommended action |
| Provenance | Empty-page/source handling | Automated tests | PASS |
| Documents UI | Document list and processing state | Browser | PASS |
| Documents UI | Upload control accepts PDF, PNG, and JPG | Browser/static/API tests | PASS |
| Documents UI | Upload and local ingestion endpoint | API/real OCR tests | PASS |
| Artifacts | TXT/CSV/JSON/XLSX/DOCX/PPTX generation | Artifact tests | PASS |
| Artifacts | Output validation before promotion | Automated tests | PASS |
| Artifacts | SHA-256 registration and verification | Automated tests and browser | PASS |
| Artifacts | Authenticated preview/download | API/browser | PASS |
| Sandbox | Staged sandbox simulation | Automated tests | PASS |
| Sandbox | Real Docker execution | Real Docker suite | PASS |
| Sandbox | `--network=none` isolation | Automated and live Docker execution | PASS |
| Sandbox | Read-only root filesystem | Real Docker tests | PASS |
| Sandbox | Memory, PID, timeout, and output limits | Real Docker tests | PASS |
| Sandbox | Path traversal and unsafe input rejection | Security tests | PASS |
| Sandbox | Browser execution of `print('deep workflow sandbox pass')` | Live UI | PASS, status SUCCESS |
| Sovereignty | Strict allow-list for loopback services | Tier A/B tests | PASS |
| Sovereignty | Public, private, metadata, alternate-representation, and redirect blocking | Security tests | PASS |
| Sovereignty | Synchronous and asynchronous HTTP transports | Tier A/B tests | PASS |
| Sovereignty | Network-event audit ledger | API/browser | PASS |
| Sovereignty | Content Security Policy and no external CDN dependencies | Browser-egress/static tests | PASS |
| Sovereignty | Independent socket observer and negative control | Tier C tests/manual evidence | PASS |
| Audit | Authenticated workspace-filtered audit endpoint | API/browser | PASS |
| Audit | Run, tool, approval, and network traceability | Automated/browser | PASS |
| CLI | `--help` and command hierarchy | Live CLI | PASS |
| CLI | `status` | Live CLI | PASS; SQLite, Chroma/FastEmbed, Ollama, Llama, and Moondream detected |
| CLI | `workspace list` | Live CLI | PASS |
| CLI | `agent list --workspace 1` | Live CLI | PASS |
| CLI | `knowledge list --workspace 1` | Live CLI | PASS |
| CLI | `approvals list` | Live CLI | PASS |
| CLI | `run history --workspace 1` | Live CLI | PASS |
| Browser | Dashboard | Fresh browser sweep | PASS |
| Browser | Workspaces | Fresh browser sweep | PASS |
| Browser | Documents | Fresh browser sweep | PASS |
| Browser | Agents | Fresh browser sweep | PASS |
| Browser | Approvals | Fresh browser sweep | PASS |
| Browser | Artifacts | Fresh browser sweep | PASS |
| Browser | Audit | Fresh browser sweep | PASS |
| Browser | Sandbox | Fresh browser sweep | PASS |
| Browser | Sovereignty | Fresh browser sweep | PASS |
| Browser | JavaScript console errors during view sweep | Browser inspection | PASS; none observed |

## 3. Activity Console and Conversational Control

### Verified interaction behavior

| Interaction | Outcome |
|---|---|
| Typed text visibility | PASS; entered text is legible |
| Submit with Enter | PASS |
| Submit with `>` / SEND button | PASS |
| `hello` | PASS; replies conversationally with the active identity |
| `help` / `what can you do` | PASS; returns current examples and explains free-form fallback |
| `who am I` / `my role` | PASS; reports local identity, role, and workspace scope |
| `system status` | PASS; refreshes readiness and sovereignty telemetry |
| `show policy` | PASS; displays strict zero-egress policy |
| `switch identity` / `login` | PASS; opens local persona authentication |
| `logout` / `terminate session` | PASS; purges the browser session token |
| `open documents` / `upload a document` / `show OCR` | PASS; opens Documents |
| `show agents` | PASS; opens Agents |
| `show pending approvals` / `review interlocks` | PASS; opens Approvals |
| `list artifacts` / `show deliverables` | PASS; opens Artifacts |
| `show audit logs` | PASS; opens Audit |
| `open sandbox` / `run code` | PASS; opens Sandbox without bypassing its controls |
| `show sovereignty` / `show network events` | PASS; opens Sovereignty |
| `go to dashboard` | PASS; returns to Dashboard |
| Persistent command bar after navigation | PASS; remains available on every non-dashboard view |
| Free-form `analyze p101a` | PASS; dispatched to Agent 1 and completed via local Ollama |
| Arbitrary non-empty natural-language prompt | PASS by design; dispatched to `/api/v1/runs` for the local agent |
| `clear` | PASS; clears the activity stream |
| `reset` | PASS; resets the visible workflow state to standby |

### What the box accepts

The input accepts any non-empty text. CogniShift first checks deterministic local control intents. Navigation, identity, status, policy, reset, and clear requests are handled immediately in the browser. Any other request is submitted to workspace 1, Agent 1, and processed by the local agent runtime. File upload still requires selecting a local file, approvals still require authorized human identities, and code execution still uses the hardened Docker sandbox; conversational control does not bypass those safeguards.

### Recommended professor demonstration commands

Use these in order:

1. `hello`
2. `what can you do`
3. `show sovereignty`
4. `open documents`
5. `show pending approvals`
6. `list artifacts`
7. `open sandbox`
8. `go to dashboard`
9. `analyze p101a`

`analyze p101a` completed in approximately 20 seconds during this validation. Local-model latency varies with GPU/CPU load. The earlier advertised phrase `trip emergency` was removed from the prompt because a 3B model interpreted it inconsistently and returned an empty completion after approximately 64 seconds. Demonstrate the pre-seeded Four-Eyes approval card for the safety flow instead of relying on that ambiguous phrase.

## 4. Automated Test Inventory

| Test module | Checks |
|---|---:|
| `test_audit_adversarial.py` | 20 |
| `test_audit_phase4_gate.py` | 8 |
| `test_audit_remediation.py` | 7 |
| `test_auth_and_audit_api.py` | 6 |
| `test_database.py` | 4 |
| `test_demo_auth.py` | 11 |
| `test_engine.py` | 7 |
| `test_frontend_api_integration.py` | 3 |
| `test_frontend_console_control.py` | 3 |
| `test_knowledge_boundary.py` | 6 |
| `test_phase0_security.py` | 5 |
| `test_phase1_router.py` | 5 |
| `test_phase2a_tool_calling.py` | 7 |
| `test_phase2b_agent_loop.py` | 3 |
| `test_phase3_artifacts.py` | 12 |
| `test_phase4_real_sandbox.py` | 16 |
| `test_phase4_sandbox.py` | 25 |
| `test_phase5_document_processing.py` | 27 |
| `test_phase5_real_ocr.py` | 3 |
| `test_phase5_real_vision.py` | 5 |
| `test_phase6_browser_egress.py` | 4 |
| `test_phase6_tier_a_policy.py` | 19 |
| `test_phase6_tier_b_real_enforcement.py` | 7 |
| `test_phase6_tier_c_observation.py` | 2 |
| `test_providers.py` | 6 |
| `test_security_regression.py` | 5 |
| **Total** | **226** |

Definitive command:

```powershell
python -m pytest -q --basetemp .pytest-tmp-isolation-proof
```

Result: **226 passed, 0 failed, 0 skipped**. Three non-failing warnings remain: one Starlette AnyIO deprecation warning and two Windows Proactor cleanup warnings emitted by the real Docker PID-limit test.

## 5. Test-Data Isolation Proof

The live server was stopped and live table counts were captured immediately before and after the complete suite.

| Live table | Before | After | Difference |
|---|---:|---:|---:|
| `workspaces` | 29 | 29 | 0 |
| `agent_definitions` | 58 | 58 | 0 |
| `knowledge_sources` | 49 | 49 | 0 |
| `agent_runs` | 239 | 239 | 0 |
| `approval_requests` | 67 | 67 | 0 |
| `network_events` | 1031 | 1031 | 0 |

Result: **PASS**. The entire test suite uses disposable SQLite, Chroma, upload, credential, and fixture locations and removes them at session completion.

## 6. Documentation Audit

Every retained Markdown file was reviewed and updated. An authoritative documentation map was added at `docs/README.md`. Nine stale, duplicated, or superseded Markdown files were removed:

- `information.md`
- `implementation_plan.md`
- `docs/SIH_DEMO_RUNBOOK.md`
- `docs/REPOSITORY_CLEANUP_AUDIT.md`
- `docs/PHASE7_SIMULATION_GAPS.md`
- `docs/PHASE7_MANUAL_PRODUCT_AUDIT.md`
- `docs/MANUAL_RUNBOOK.md`
- `docs/AUDIT_VERIFICATION_MATRIX.md`
- `docs/AUDIT_REMEDIATION_REPORT.md`

The CLI documentation was corrected to use the implemented `--workspace` option instead of the invalid `--workspace-id` form.

## 7. Open Observations and Demo Hygiene

These do not invalidate the successful test result, but should be understood before presentation:

1. **Existing live demo data is not pristine.** Historical test runs created 29 workspaces, 58 agents, 49 knowledge sources, 239 runs, and 67 approvals before isolation was fixed. Do not delete these implicitly. Run the documented demo reset/seed workflow when you are ready to prepare the professor demonstration.
2. **One stale source record is marked `DELETION_FAILED`.** `Turbine_Manual.pdf` has that historical state; `P-101A_Inspection_Report.pdf`, `Pump_Manual.pdf`, and `Pump_Maintenance_SOP.pdf` were completed. Reset/seed before the demo to avoid showing the stale record.
3. **Approval completion latency can be high.** The repaired live Jane → Rohit flow succeeded without HTTP 500, but the second request waited about 97 seconds while the paused local agent resumed. The authorization was correct; the delay is local inference/execution latency.
4. **Ambiguous natural-language commands depend on the selected small model.** Deterministic control commands are reliable. Free-form results and duration vary with model capability and hardware.
5. **The first attempted isolation configuration used incorrect environment variable names.** It did not isolate persistence and added historical demo records. The correction now sets the exact `DATA_DIR`, `DATABASE_PATH`, `CHROMA_PATH`, `UPLOAD_DIR`, and `AUTH_STORE_PATH` variables before importing CogniShift. The zero-difference proof above validates the final implementation.

## 8. Final Assessment

The current local working tree is suitable for a supervised professor demonstration after running the documented reset/seed procedure. The strongest reliable showcase is:

1. local demo identity login;
2. conversational console navigation;
3. scanned P-101A provenance through RapidOCR;
4. a local `analyze p101a` run;
5. the pre-seeded dual Four-Eyes approval flow;
6. artifact integrity/download;
7. real Docker sandbox execution; and
8. the sovereignty ledger plus independent network observer.

No frontend files are included in the requested GitHub push. Backend, tests, scripts, and documentation are eligible for that push after staged-content verification.
