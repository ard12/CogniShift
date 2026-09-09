# CogniShift sandbox capabilities and deep test report
Date: 5 September 2026

## Verified outcome

- Existing real-container suite: 16 passed.
- Expanded real/container and regression run: 31 passed.
- Full application suite after main fixes: 252 passed, zero skipped, one unrelated dependency deprecation warning (108.65 seconds).
- Final focused suite after failed-staging cleanup and two additional regressions: 19 passed (18.47 seconds). The full suite was not rerun after those final additions.
- Final Docker container listing: no remaining cognishift-sbx containers.
- Actual local Docker engine: 29.7.2. No image pulls or dependency downloads were performed.
- Tests used isolated application persistence. No live plant actions were performed.

## What it can actually run

| Capability | Evidence / boundary |
| --- | --- |
| Python | Installed image reports Python 3.12.14. Backend always invokes python3 with a staged .py entrypoint. |
| Engineering calculations | Real math, decimal and statistics calculation probe passed. No claim of engineering-design certification. |
| CSV and JSON | Real parsing, serialization and output writing passed. |
| SQLite | In-memory SQL calculation passed. Host application database is not mounted. |
| Temporary files | Python temporary-file read/write passed inside container /tmp. |
| Child processes | A child Python process executed successfully inside the same restricted container. This is not host execution. |
| Input files | Read-only staged inputs tested; host-side input content remained unchanged. Inputs must come through workspace path checks. |
| Deliverables | Real CSV creation, application artifact registration, nonempty generated execution ID and staging cleanup passed end to end. |
| Errors | Missing pandas, Python syntax error and explicit ValueError returned runtime_error and nonzero exit codes. |
| NumPy / pandas / plotting | Not installed: numpy, pandas, matplotlib, scipy, sympy. |
| Office / image / PDF libraries | Not installed: openpyxl, docx, pptx, PIL, fitz. Application-level document generators are separate tools, not installed sandbox libraries. |
| HTTP libraries | requests not installed. Python stdlib networking exists, but the container has network disabled. |
| Other languages / GPU | No language-selection API or GPU allocation in the sandbox command. Not validated for Node, Java, C/C++, CUDA or model inference. |
| Package installation | No automatic dependency installation; image pulls are forbidden. Approved offline image provisioning is separate deployment work. |

## Limits and security boundaries

- Submitted code: 1–100,000 characters. Entrypoint: restricted .py filename.
- Request timeout: 5–120 seconds; server maximum can reduce it (current maximum 120).
- CPU request: 0.1–2 cores; effective service cap currently 1 core.
- Memory request: 64–1024 MiB; effective service cap currently 512 MiB. Swap capped equal to memory.
- PID cap: 64. Real bounded process-creation and memory-pressure tests passed, but existing assertions are not comprehensive kernel-limit certification.
- Network: --network none; real denied-connect test passed.
- Root filesystem, source and input mounts: read-only. Output mount: writable.
- User: UID/GID 10001; all Linux capabilities dropped; no-new-privileges enabled. Actual /proc flags checked.
- No Docker socket mounted; host environment-secret probe passed.
- /tmp: 64 MiB tmpfs with noexec/nosuid/nodev.
- stdout and stderr: each retained up to 65,536 bytes; remaining bytes drained without unbounded buffering. Real 200,000-character streams passed.
- Output promotion: top-level txt, csv, json, docx, xlsx and pptx only. Executable/script formats are rejected. Office files require structural validation.
- Promotion limits: up to 10 entries examined, 10 MiB per file. Nested outputs, images, PDFs and Python source files are not promoted.
- Timeout cleanup is awaited; no test containers remained at final inspection.

## Bugs fixed in this pass

1. Health check now queries daemon info with a bounded wait, rather than reporting healthy when only the CLI exists.
2. Service-generated execution ID and trusted workspace/run IDs are propagated to backend requests.
3. Server sandbox-disable switch is enforced before staging.
4. Server CPU, memory and timeout caps limit requested resources.
5. stdout/stderr are bounded while reading, not only after buffering the entire process output.
6. Timeout container removal and CLI teardown are awaited. Previous unclosed-transport warnings did not recur in the fixed focused run.
7. Hardlinked outputs are rejected before promotion.
8. Dot/dot-dot input destinations and unsafe execution-ID characters are rejected.
9. Reused staging IDs fail without deleting an existing execution directory.
10. Failed staging cleans partial source/input directories.

## Remaining hardening gaps — not certified solved

- Writable host output mount has no runtime disk quota. Post-execution size/count filters do not prevent temporary host disk consumption during execution.
- No aggregate output-byte cap is currently enforced by the promoter.
- Request cancellation/server crash recovery deserves a separate durable container-reaper design; this pass verified normal completion and timeout cleanup.
- OOM status classification still relies partly on exit code/stderr; a killed process may report runtime_error rather than resource_exceeded.
- Some inherited isolation tests have weak negative assertions. Passing them is not equivalent to a penetration test or proof against container escapes.
- No multi-user load/concurrency soak test, OS escape test or physical air-gap certification.
- Changes are local and not pushed. Restart the app process to guarantee it loads the latest sandbox modules.

## Demo examples

With an agent allowed to use execute_code, request:
- “Use Python's standard library to calculate the mean, minimum and maximum of these readings: 12, 15, 18.”
- “Run and verify a Python calculation of the area of a pipe with internal radius 0.05 metres.”
- “Write a CSV summary to /workspace/output/summary.csv and promote it as an artifact.”

The agent still needs to select the code tool correctly and provide valid arguments; these examples describe verified sandbox capabilities, not a fresh conversational UI acceptance test. Do not promise pandas, plots, Word or Excel libraries inside the current sandbox image.

## Automated sandbox outcomes from full-suite evidence

All rows below passed. Final focused evidence additionally covers invalid-input cleanup and server-cap override tests.

| Module | Test | Seconds |
| --- | --- | --- |
| tests.test_phase4_real_sandbox | test_real_sandbox_basic_execution | 1.109 |
| tests.test_phase4_real_sandbox | test_real_sandbox_non_root_execution | 0.999 |
| tests.test_phase4_real_sandbox | test_real_sandbox_network_isolation | 1.125 |
| tests.test_phase4_real_sandbox | test_real_sandbox_read_only_root_filesystem | 1.064 |
| tests.test_phase4_real_sandbox | test_real_sandbox_read_only_source_mount | 1.068 |
| tests.test_phase4_real_sandbox | test_real_sandbox_read_only_input_mount | 1.002 |
| tests.test_phase4_real_sandbox | test_real_sandbox_writable_output_mount | 1.104 |
| tests.test_phase4_real_sandbox | test_real_sandbox_host_secret_isolation | 1.105 |
| tests.test_phase4_real_sandbox | test_real_sandbox_environment_isolation | 1.117 |
| tests.test_phase4_real_sandbox | test_real_sandbox_timeout_and_removal | 5.862 |
| tests.test_phase4_real_sandbox | test_real_sandbox_memory_limit | 2.370 |
| tests.test_phase4_real_sandbox | test_real_sandbox_pid_limit | 1.213 |
| tests.test_phase4_real_sandbox | test_real_sandbox_output_symlink_rejection | 0.962 |
| tests.test_phase4_real_sandbox | test_real_sandbox_output_extension_policy | 0.077 |
| tests.test_phase4_real_sandbox | test_real_sandbox_artifact_promotion | 0.076 |
| tests.test_phase4_real_sandbox | test_real_sandbox_missing_runtime_fails_closed | 0.057 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_empty_code | 0.030 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_oversized_code | 0.023 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[../evil.py] | 0.021 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[../../main.py] | 0.025 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[sub/main.py] | 0.023 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[main.sh] | 0.030 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[script.exe] | 0.021 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[main.py\x00] | 0.024 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[main] | 0.022 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_out_of_bounds_timeout[0] | 0.024 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_out_of_bounds_timeout[4] | 0.024 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_out_of_bounds_timeout[121] | 0.038 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_out_of_bounds_timeout[-10] | 0.023 |
| tests.test_phase4_sandbox | test_staging_valid_inputs | 0.048 |
| tests.test_phase4_sandbox | test_staging_strictly_rejects_knowledge_subsystem | 0.032 |
| tests.test_phase4_sandbox | test_staging_strictly_rejects_path_traversal | 0.033 |
| tests.test_phase4_sandbox | test_simulated_backend_executes_zero_code | 0.025 |
| tests.test_phase4_sandbox | test_simulated_backend_trigger_runtime_error | 0.023 |
| tests.test_phase4_sandbox | test_output_validation_rejects_executable_scripts | 0.070 |
| tests.test_phase4_sandbox | test_docker_backend_fails_closed_when_unavailable | 0.058 |
| tests.test_phase4_sandbox | test_execute_code_denied_with_empty_allowlist | 0.022 |
| tests.test_phase4_sandbox | test_execute_code_denied_when_not_in_allowlist | 0.026 |
| tests.test_phase4_sandbox | test_execute_code_classified_as_sensitive | 0.034 |
| tests.test_phase4_sandbox | test_execute_code_pauses_when_agent_requires_approval | 0.111 |
| tests.test_phase4_sandbox | test_coding_agent_retry_loop_bounded | 0.872 |
| tests.test_sandbox_deep | test_real_capability[engineering_math] | 2.834 |
| tests.test_sandbox_deep | test_real_capability[csv_json_sqlite] | 1.433 |
| tests.test_sandbox_deep | test_real_capability[subprocess_inside_container] | 1.476 |
| tests.test_sandbox_deep | test_real_capability[temporary_files] | 1.485 |
| tests.test_sandbox_deep | test_real_capability[missing_pandas] | 1.452 |
| tests.test_sandbox_deep | test_real_capability[syntax_error] | 1.291 |
| tests.test_sandbox_deep | test_real_capability[runtime_traceback] | 1.248 |
| tests.test_sandbox_deep | test_real_capability[bounded_streams] | 1.284 |
| tests.test_sandbox_deep | test_real_capability[privileges] | 1.763 |
| tests.test_sandbox_deep | test_real_service_generated_id_promotion_and_cleanup | 1.663 |
| tests.test_sandbox_deep | test_hardlink_output_rejected | 0.031 |
| tests.test_sandbox_deep | test_directory_input_names_rejected[.] | 0.028 |
| tests.test_sandbox_deep | test_directory_input_names_rejected[..] | 0.027 |
| tests.test_sandbox_deep | test_health_requires_daemon | 0.048 |
| tests.test_sandbox_deep | test_bounded_reader_drains_entire_stream | 0.048 |
| tests.test_sandbox_deep | test_disabled_sandbox_cannot_stage_or_execute | 0.030 |
| tests.test_sandbox_deep | test_duplicate_execution_does_not_erase_files | 0.054 |

Raw results: sandbox-deep-tests.xml and sandbox-deep-capabilities.xml.

