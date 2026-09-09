# CogniShift system audit — 5 September 2026

## Verdict

Several confirmed defects were repaired. This is a code audit plus an automated regression run and local service checks, **not certification that every live UI workflow works**.

Final full-suite result: **222 passed, 13 skipped, 0 failed** (25.68 seconds; one dependency deprecation warning). All 235 individual outcomes are listed below. Tests use isolated persistence, not the live application database.

## Repairs

- Approval stage 1 uses a conditional update requiring an empty first-reviewer field. Stage 2 requires the same first reviewer observed during authorization and an empty second-reviewer field. Concurrent stale requests cannot overwrite a sign-off.
- Any failed execution step now makes the overall run failed, even if another step completed.
- Approved tool exceptions and explicit tool-error responses produce a failed run, preserve the error and block pending dependent steps. Added two execution regression cases.
- Non-sandbox tools returning explicit error prefixes no longer appear as completed steps.
- Approval documents use recorded request, parameters, reviewer identities and output instead of invented P-101A readings, root causes, recovery claims or zero-egress certification. Filenames include run ID.
- Console messages use DOM textContent rather than interpolating operator/model text into HTML. This repairs the console sink, not every dynamic HTML sink in the UI.
- Restarted the stopped local FastAPI backend on 127.0.0.1:8000. Health response confirms local mode, initialized database and reachable Ollama.

## Runtime checks and remaining risks

| Area | Outcome |
| --- | --- |
| Backend availability | Initially connection refused; restarted successfully and status endpoint returned healthy local configuration. This can explain fetch failures while the service was stopped, but does not prove every earlier OCR error had this cause. |
| Local models | Ollama lists llama3.2:3b and moondream:latest. Full-suite model and OCR tests passed; model availability alone does not establish answer quality. |
| Docker | CLI installed; Linux-engine named pipe missing. Started Docker Desktop, then retried: engine still unavailable. Separate sandbox test run: 3 passed, 13 skipped. No model/image downloads performed by this audit. |
| Conversation | Existing console has exact navigation commands and structured agent dispatch, but dispatch sends a single input with hard-coded agent ID 1. Persistent multi-turn history is not implemented. |
| Plan truthfulness | Remaining paths still mark pending steps completed after a final answer or approved action without executing each step. Requires further orchestration work before claiming fully general end-to-end execution. |
| Post-approval synthesis | A model-provider exception after successful tool execution can leave a run resuming. Durable finalization/recovery remains needed. |
| Frontend | Existing static/auth/command tests passed. No fresh interactive browser walk-through in this audit; remaining innerHTML sites and progress indicators need separate review. |
| Approval concurrency | Conditional-update repair reviewed; existing two-stage SQLite API regression passed. No deterministic concurrent stress test added. |
| Scanned report to deliverable | OCR/document/artifact regression coverage passed; the complete live professor-demo flow was not rerun in the browser. |
| Sovereignty | Policy/enforcement/observation tests passed. This is not a new host-wide packet capture or physical air-gap certification. |
| GitHub | This audit's changes remain local; no new commit/push. Existing user changes preserved. Frontend excluded from publication as requested. |

## Interpretation of evidence

Many tests use simulated providers or mocks; a passing test proves only its assertions. Earlier documentation claiming universal live acceptance or zero skips should not be treated as current evidence. Historical documents were not mass-deleted. This report supersedes earlier blanket pass claims for this audit.

Initial verification attempts encountered a protected pytest temporary directory; using a new explicit test directory resolved it. Two newly added test assertions initially referenced a plan field absent from the response model; corrected to inspect persisted plan state, then reran the entire suite successfully.

Raw machine-readable evidence: audit-sept5-tests.xml and audit-sept5-docker.xml alongside this report.

## Individual automated outcomes

| Test module | Test | Outcome | Seconds |
| --- | --- | --- | --- |
| tests.test_audit_adversarial | test_adversarial_prompt_keyword_cannot_trigger_tool_execution | PASS | 0.021 |
| tests.test_audit_adversarial | test_adversarial_model_refusal_prevents_tool_and_approval | PASS | 0.038 |
| tests.test_audit_adversarial | test_known_source_credential_strings_cannot_authenticate | PASS | 0.027 |
| tests.test_audit_adversarial | test_invalid_api_key_rejected_with_401 | PASS | 0.012 |
| tests.test_audit_adversarial | test_disabled_or_revoked_credential_rejected | PASS | 0.013 |
| tests.test_audit_adversarial | test_client_controlled_role_header_ignored | PASS | 0.027 |
| tests.test_audit_adversarial | test_workspace_idor_cross_tenant_access_blocked | PASS | 0.012 |
| tests.test_audit_adversarial | test_self_approval_denied_by_four_eyes | PASS | 0.009 |
| tests.test_audit_adversarial | test_concurrent_resume_executes_tool_exactly_once | PASS | 0.123 |
| tests.test_audit_adversarial | test_adversarial_tool_schema_empty_sensor_id_produces_zero_execution | PASS | 0.045 |
| tests.test_audit_adversarial | test_adversarial_tool_schema_oversized_sensor_id_produces_zero_execution | PASS | 0.016 |
| tests.test_audit_adversarial | test_adversarial_tool_schema_illegal_characters_produces_zero_execution | PASS | 0.010 |
| tests.test_audit_adversarial | test_adversarial_tool_schema_empty_high_risk_reason_produces_zero_execution | PASS | 0.012 |
| tests.test_audit_adversarial | test_parse_tool_call_validation_failure_returns_false_contract | PASS | 0.009 |
| tests.test_audit_adversarial | test_adversarial_provider_protocol_empty_response_fails | PASS | 0.033 |
| tests.test_audit_adversarial | test_adversarial_provider_protocol_whitespace_only_fails | PASS | 0.044 |
| tests.test_audit_adversarial | test_adversarial_provider_protocol_garbage_response_fails | PASS | 0.037 |
| tests.test_audit_adversarial | test_adversarial_provider_protocol_malformed_json_fails | PASS | 0.033 |
| tests.test_audit_adversarial | test_adversarial_provider_protocol_timeout_fails | PASS | 0.085 |
| tests.test_audit_adversarial | test_approval_crash_recovery_resumption_succeeds | PASS | 0.310 |
| tests.test_audit_phase4_gate | test_remediation_generic_file_write_subsystem_directories_strictly_denied | PASS | 0.018 |
| tests.test_audit_phase4_gate | test_remediation_generic_directory_create_subsystem_directories_strictly_denied | PASS | 0.019 |
| tests.test_audit_phase4_gate | test_remediation_generic_file_read_and_list_internal_subsystems_denied | PASS | 0.025 |
| tests.test_audit_phase4_gate | test_remediation_canonical_immutability_denies_all_path_variants | PASS | 0.087 |
| tests.test_audit_phase4_gate | test_remediation_empty_allowed_tools_strictly_denies_every_tool | PASS | 0.015 |
| tests.test_audit_phase4_gate | test_remediation_specific_allowed_tools_enforcement | PASS | 0.013 |
| tests.test_audit_phase4_gate | test_remediation_file_read_max_bytes_defense_in_depth | PASS | 0.031 |
| tests.test_audit_phase4_gate | test_remediation_end_to_end_knowledge_boundary_confidentiality | PASS | 0.184 |
| tests.test_audit_remediation | test_aud004_resume_completed_run_strictly_enforces_cas_invariant | PASS | 0.019 |
| tests.test_audit_remediation | test_aud006_parse_agent_action_tool_key_without_action_field | PASS | 0.002 |
| tests.test_audit_remediation | test_aud006_parse_agent_action_tool_name_key | PASS | 0.002 |
| tests.test_audit_remediation | test_aud006_parse_agent_action_name_key | PASS | 0.002 |
| tests.test_audit_remediation | test_aud006_parse_agent_action_markdown_json_block | PASS | 0.002 |
| tests.test_audit_remediation | test_aud003_image_path_outside_data_dir_raises_security_error | PASS | 0.028 |
| tests.test_audit_remediation | test_aud003_image_path_inside_data_dir_permitted | PASS | 0.041 |
| tests.test_auth_and_audit_api | test_auth_me_unauthorized | PASS | 0.005 |
| tests.test_auth_and_audit_api | test_auth_me_invalid_token | PASS | 0.005 |
| tests.test_auth_and_audit_api | test_auth_me_valid_tokens | PASS | 0.005 |
| tests.test_auth_and_audit_api | test_demo_personas_never_returns_credentials | PASS | 0.005 |
| tests.test_auth_and_audit_api | test_audit_endpoint_access_control | PASS | 0.036 |
| tests.test_auth_and_audit_api | test_real_sqlite_row_supports_two_stage_approval | PASS | 0.026 |
| tests.test_conversational_protocol | test_frontend_deterministic_commands_vs_agent_queries | PASS | 0.014 |
| tests.test_conversational_protocol | test_conversational_final_answer_with_real_citations | PASS | 0.041 |
| tests.test_conversational_protocol | test_discussion_about_action_does_not_execute_tool | PASS | 0.043 |
| tests.test_conversational_protocol | test_action_request_proposes_tool_and_pauses_for_approval | PASS | 0.044 |
| tests.test_conversational_protocol | test_chat_failure_missing_tool_argument_rejected_and_fails_closed | PASS | 0.038 |
| tests.test_conversational_protocol | test_chat_failure_garbage_output_fails_closed | PASS | 0.038 |
| tests.test_conversational_protocol | test_chat_failure_no_retrieval_does_not_manufacture_citations | PASS | 0.040 |
| tests.test_database | test_init_db | PASS | 0.018 |
| tests.test_database | test_create_workspace | PASS | 0.023 |
| tests.test_database | test_create_agent | PASS | 0.018 |
| tests.test_database | test_seed_data | PASS | 0.029 |
| tests.test_demo_auth | test_demo_session_disabled_by_default | PASS | 0.006 |
| tests.test_demo_auth | test_demo_session_rejects_non_loopback | PASS | 0.005 |
| tests.test_demo_auth | test_local_demo_persona_creates_ephemeral_verified_session[operator-operator_sam-operator] | PASS | 0.006 |
| tests.test_demo_auth | test_local_demo_persona_creates_ephemeral_verified_session[supervisor-supervisor_jane-supervisor] | PASS | 0.005 |
| tests.test_demo_auth | test_local_demo_persona_creates_ephemeral_verified_session[administrator-admin_rohit-administrator] | PASS | 0.005 |
| tests.test_demo_auth | test_changed_credential_store_reloads_without_server_restart | PASS | 0.017 |
| tests.test_demo_auth | test_sandbox_api_stages_demo_input_as_workspace_relative_path | PASS | 0.010 |
| tests.test_demo_auth | test_sandbox_api_rejects_unapproved_input_filename | PASS | 0.005 |
| tests.test_engine | test_parse_tool_call | PASS | 0.012 |
| tests.test_engine | test_direct_answer_run | PASS | 0.045 |
| tests.test_engine | test_safe_tool_execution | PASS | 0.038 |
| tests.test_engine | test_high_risk_tool_pauses_for_approval | PASS | 0.032 |
| tests.test_engine | test_resume_after_approval | PASS | 0.122 |
| tests.test_engine | test_approved_tool_failure_is_not_reported_as_success[failure0] | PASS | 0.050 |
| tests.test_engine | test_approved_tool_failure_is_not_reported_as_success[Error: actuator unavailable] | PASS | 0.049 |
| tests.test_engine | test_resume_after_rejection | PASS | 0.042 |
| tests.test_engine | test_runs_api_endpoints | PASS | 0.051 |
| tests.test_frontend_api_integration | test_frontend_backing_endpoints_with_auth | PASS | 6.116 |
| tests.test_frontend_api_integration | test_four_eyes_authorization_rejection_for_operator | PASS | 0.009 |
| tests.test_frontend_auth_ui | test_frontend_has_no_hardcoded_api_tokens_and_keeps_strict_csp | PASS | 0.002 |
| tests.test_frontend_auth_ui | test_sovereignty_ledger_uses_current_network_event_schema | PASS | 0.004 |
| tests.test_frontend_auth_ui | test_console_command_input_has_explicit_visible_foreground | PASS | 0.002 |
| tests.test_frontend_console_control | test_console_routes_every_primary_view_and_preserves_agent_fallback | PASS | 0.002 |
| tests.test_frontend_console_control | test_console_supports_conversational_and_session_commands | PASS | 0.002 |
| tests.test_frontend_console_control | test_conversational_command_bar_remains_available_outside_dashboard | PASS | 0.003 |
| tests.test_frontend_static_ui | test_static_and_root_serving | PASS | 0.012 |
| tests.test_knowledge_boundary | test_agent_allowed_source_filtering | PASS | 0.075 |
| tests.test_knowledge_boundary | test_agent_empty_sources_fails_closed | PASS | 0.012 |
| tests.test_knowledge_boundary | test_agent_execution_enforces_knowledge_boundary | PASS | 0.039 |
| tests.test_knowledge_boundary | test_cross_workspace_source_filtered_out | PASS | 0.039 |
| tests.test_knowledge_boundary | test_purge_knowledge_source_removes_chunks_from_chroma | PASS | 0.033 |
| tests.test_knowledge_boundary | test_chroma_purge_failure_prevents_false_success | PASS | 0.025 |
| tests.test_phase0_security | test_path_traversal_rejected | PASS | 0.002 |
| tests.test_phase0_security | test_valid_workspace_path_resolution | PASS | 0.003 |
| tests.test_phase0_security | test_four_eyes_identity_enforced | PASS | 0.002 |
| tests.test_phase0_security | test_workspace_access_control | PASS | 0.001 |
| tests.test_phase0_security | test_cors_origins_restricted | PASS | 0.001 |
| tests.test_phase1_router | test_task_classification | PASS | 0.002 |
| tests.test_phase1_router | test_model_routing_coding | PASS | 0.002 |
| tests.test_phase1_router | test_model_routing_vram_constraint | PASS | 0.003 |
| tests.test_phase1_router | test_model_routing_vision | PASS | 0.002 |
| tests.test_phase1_router | test_model_registry_extensibility | PASS | 0.002 |
| tests.test_phase2a_tool_calling | test_parse_tool_call_proposal | PASS | 0.002 |
| tests.test_phase2a_tool_calling | test_parse_final_answer | PASS | 0.002 |
| tests.test_phase2a_tool_calling | test_parse_plain_text_fallback | PASS | 0.002 |
| tests.test_phase2a_tool_calling | test_validate_tool_call_valid | PASS | 0.002 |
| tests.test_phase2a_tool_calling | test_validate_tool_call_missing_parameters | PASS | 0.001 |
| tests.test_phase2a_tool_calling | test_validate_tool_call_permission_denied | PASS | 0.001 |
| tests.test_phase2a_tool_calling | test_central_risk_policy_forces_hitl | PASS | 0.002 |
| tests.test_phase2b_agent_loop | test_plan_creation_bounded_to_max_steps | PASS | 0.012 |
| tests.test_phase2b_agent_loop | test_plan_serialization_roundtrip | PASS | 0.011 |
| tests.test_phase2b_agent_loop | test_plan_preservation_across_hitl_pause_and_resumption | PASS | 0.117 |
| tests.test_phase3_artifacts | test_standardized_workspace_layout_creation | PASS | 0.016 |
| tests.test_phase3_artifacts | test_safe_file_write_and_read | PASS | 0.039 |
| tests.test_phase3_artifacts | test_file_tools_path_traversal_strictly_rejected | PASS | 0.017 |
| tests.test_phase3_artifacts | test_generic_file_write_cannot_overwrite_registered_artifact | PASS | 0.069 |
| tests.test_phase3_artifacts | test_generate_and_validate_docx | PASS | 0.078 |
| tests.test_phase3_artifacts | test_generate_and_validate_xlsx_with_formula_sanitization | PASS | 0.070 |
| tests.test_phase3_artifacts | test_generate_and_validate_pptx | PASS | 0.092 |
| tests.test_phase3_artifacts | test_structural_validation_failure_leaves_no_orphan_or_db | PASS | 0.020 |
| tests.test_phase3_artifacts | test_two_runs_same_filename_produce_independent_artifacts | PASS | 0.097 |
| tests.test_phase3_artifacts | test_register_artifact_with_cross_workspace_run_id_rejected | PASS | 0.024 |
| tests.test_phase3_artifacts | test_tamper_detection_refuses_modified_download | PASS | 0.071 |
| tests.test_phase3_artifacts | test_cross_tenant_idor_blocked_on_artifacts | PASS | 0.019 |
| tests.test_phase4_real_sandbox | test_real_sandbox_basic_execution | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_non_root_execution | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_network_isolation | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_read_only_root_filesystem | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_read_only_source_mount | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_read_only_input_mount | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_writable_output_mount | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_host_secret_isolation | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_environment_isolation | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_timeout_and_removal | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_memory_limit | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_pid_limit | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_output_symlink_rejection | SKIPPED — Docker engine unavailable | 0.000 |
| tests.test_phase4_real_sandbox | test_real_sandbox_output_extension_policy | PASS | 0.029 |
| tests.test_phase4_real_sandbox | test_real_sandbox_artifact_promotion | PASS | 0.031 |
| tests.test_phase4_real_sandbox | test_real_sandbox_missing_runtime_fails_closed | PASS | 0.019 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_empty_code | PASS | 0.010 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_oversized_code | PASS | 0.008 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[../evil.py] | PASS | 0.009 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[../../main.py] | PASS | 0.008 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[sub/main.py] | PASS | 0.008 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[main.sh] | PASS | 0.030 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[script.exe] | PASS | 0.008 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[main.py\x00] | PASS | 0.008 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_invalid_entrypoint[main] | PASS | 0.008 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_out_of_bounds_timeout[0] | PASS | 0.008 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_out_of_bounds_timeout[4] | PASS | 0.008 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_out_of_bounds_timeout[121] | PASS | 0.008 |
| tests.test_phase4_sandbox | test_sandbox_schema_rejects_out_of_bounds_timeout[-10] | PASS | 0.027 |
| tests.test_phase4_sandbox | test_staging_valid_inputs | PASS | 0.051 |
| tests.test_phase4_sandbox | test_staging_strictly_rejects_knowledge_subsystem | PASS | 0.012 |
| tests.test_phase4_sandbox | test_staging_strictly_rejects_path_traversal | PASS | 0.011 |
| tests.test_phase4_sandbox | test_simulated_backend_executes_zero_code | PASS | 0.009 |
| tests.test_phase4_sandbox | test_simulated_backend_trigger_runtime_error | PASS | 0.009 |
| tests.test_phase4_sandbox | test_output_validation_rejects_executable_scripts | PASS | 0.024 |
| tests.test_phase4_sandbox | test_docker_backend_fails_closed_when_unavailable | PASS | 0.017 |
| tests.test_phase4_sandbox | test_execute_code_denied_with_empty_allowlist | PASS | 0.008 |
| tests.test_phase4_sandbox | test_execute_code_denied_when_not_in_allowlist | PASS | 0.008 |
| tests.test_phase4_sandbox | test_execute_code_classified_as_sensitive | PASS | 0.008 |
| tests.test_phase4_sandbox | test_execute_code_pauses_when_agent_requires_approval | PASS | 0.043 |
| tests.test_phase4_sandbox | test_coding_agent_retry_loop_bounded | PASS | 0.518 |
| tests.test_phase5_document_processing | test_file_type_detection | PASS | 0.024 |
| tests.test_phase5_document_processing | test_inspect_document_rejects_unsupported_file | PASS | 0.012 |
| tests.test_phase5_document_processing | test_inspect_document_rejects_oversized_file | PASS | 0.013 |
| tests.test_phase5_document_processing | test_inspect_document_rejects_excessive_pdf_pages | PASS | 0.014 |
| tests.test_phase5_document_processing | test_inspect_document_rejects_oversized_image_dimensions | PASS | 0.037 |
| tests.test_phase5_document_processing | test_assess_native_page_quality_good_text | PASS | 0.007 |
| tests.test_phase5_document_processing | test_assess_native_page_quality_too_short | PASS | 0.007 |
| tests.test_phase5_document_processing | test_assess_native_page_quality_garbage_replacement_chars | PASS | 0.006 |
| tests.test_phase5_document_processing | test_assess_native_page_quality_scanned_image_page_with_stray_chars | PASS | 0.007 |
| tests.test_phase5_document_processing | test_native_pdf_extraction_1_based_page_contract | PASS | 0.019 |
| tests.test_phase5_document_processing | test_render_page_to_png_bounded_dpi | PASS | 0.056 |
| tests.test_phase5_document_processing | test_mixed_pdf_page_scoped_triage | PASS | 0.269 |
| tests.test_phase5_document_processing | test_versioned_reprocessing_failure_preserves_old_generation | PASS | 0.041 |
| tests.test_phase5_document_processing | test_ocr_unavailable_fails_closed | PASS | 0.501 |
| tests.test_phase5_document_processing | test_low_ocr_confidence_marks_uncertain | PASS | 0.006 |
| tests.test_phase5_document_processing | test_vision_optional_when_unavailable_continues | PASS | 0.008 |
| tests.test_phase5_document_processing | test_vision_required_when_unavailable_raises | PASS | 0.007 |
| tests.test_phase5_document_processing | test_source_isolation_through_retriever | PASS | 0.371 |
| tests.test_phase5_document_processing | test_temporary_processing_directory_purged | PASS | 0.214 |
| tests.test_phase5_document_processing | test_prompt_injection_quarantine_in_document | PASS | 0.226 |
| tests.test_phase5_document_processing | test_versioned_reprocessing_success_retires_old_chunks | PASS | 0.382 |
| tests.test_phase5_document_processing | test_reconciliation_cleans_orphaned_directories_and_stuck_jobs | PASS | 0.035 |
| tests.test_phase5_document_processing | test_cross_workspace_processing_prevented_before_side_effects | PASS | 0.037 |
| tests.test_phase5_document_processing | test_wrap_document_data_escapes_hostile_delimiters | PASS | 0.009 |
| tests.test_phase5_document_processing | test_stale_generation_excluded_by_active_version_filter | PASS | 0.114 |
| tests.test_phase5_document_processing | test_multi_source_paired_active_version_filter | PASS | 0.142 |
| tests.test_phase5_document_processing | test_wrap_document_data_escapes_body_delimiter_breakout | PASS | 0.009 |
| tests.test_phase5_real_ocr | test_real_rapidocr_extracts_known_scanned_fixture | PASS | 2.400 |
| tests.test_phase5_real_ocr | test_real_rapidocr_full_service_pipeline | PASS | 2.869 |
| tests.test_phase5_real_ocr | test_real_ocr_missing_assets_fails_closed | PASS | 0.501 |
| tests.test_phase5_real_vision | test_real_vision_model_availability | PASS | 0.385 |
| tests.test_phase5_real_vision | test_real_vision_router_selected_identity | PASS | 0.003 |
| tests.test_phase5_real_vision | test_real_vision_inference_with_local_ollama | PASS | 1.208 |
| tests.test_phase5_real_vision | test_real_vision_missing_model_fails_closed | PASS | 0.372 |
| tests.test_phase5_real_vision | test_real_vision_inference_error_distinguished_from_unavailable | PASS | 0.010 |
| tests.test_phase6_browser_egress | test_index_html_contains_zero_external_links | PASS | 0.003 |
| tests.test_phase6_browser_egress | test_local_static_assets_exist | PASS | 0.003 |
| tests.test_phase6_browser_egress | test_browser_scanner_negative_control | PASS | 0.002 |
| tests.test_phase6_browser_egress | test_content_security_policy_header_enforced | PASS | 0.188 |
| tests.test_phase6_tier_a_policy | test_classify_ip_ipv4_loopback | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_classify_ip_ipv6_loopback | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_classify_ip_private_rfc1918 | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_classify_ip_private_ipv6_ula | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_classify_ip_link_local | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_classify_ip_public | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_network_destination_valid | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_network_destination_rejects_wildcards | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_network_destination_rejects_invalid_ports | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_policy_allows_default_loopback_ollama | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_policy_allows_default_loopback_fastapi | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_policy_blocks_unauthorized_loopback_port_in_strict | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_policy_blocks_unauthorized_private_lan | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_policy_allows_explicitly_allowlisted_private_destination | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_policy_blocks_link_local_metadata_unconditionally | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_policy_blocks_public_destinations | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_dns_rebinding_fail_closed_if_one_ip_is_public | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_dns_unresolvable_fails_closed | PASS | 0.002 |
| tests.test_phase6_tier_a_policy | test_development_mode_allows_with_warning | PASS | 0.002 |
| tests.test_phase6_tier_b_real_enforcement | test_real_ollama_loopback_allowed | PASS | 0.184 |
| tests.test_phase6_tier_b_real_enforcement | test_real_public_request_blocked_before_socket_connect | PASS | 0.175 |
| tests.test_phase6_tier_b_real_enforcement | test_real_unauthorized_lan_request_blocked | PASS | 0.178 |
| tests.test_phase6_tier_b_real_enforcement | test_real_fastembed_offline_fails_closed_when_cache_missing | PASS | 0.003 |
| tests.test_phase6_tier_b_real_enforcement | test_real_missing_ollama_model_fails_closed_without_pull | PASS | 0.180 |
| tests.test_phase6_tier_b_real_enforcement | test_approval_does_not_override_network_policy | PASS | 0.177 |
| tests.test_phase6_tier_b_real_enforcement | test_sensitive_data_not_leaked_in_network_audit | PASS | 0.180 |
| tests.test_phase6_tier_c_observation | test_observer_negative_control | PASS | 0.068 |
| tests.test_phase6_tier_c_observation | test_strict_workflow_records_zero_unauthorized_egress | PASS | 0.257 |
| tests.test_providers | test_simulated_provider_generate | PASS | 0.003 |
| tests.test_providers | test_simulated_provider_health | PASS | 0.016 |
| tests.test_providers | test_simulated_provider_image | PASS | 0.015 |
| tests.test_providers | test_factory_simulated_mode | PASS | 0.002 |
| tests.test_providers | test_factory_rejects_external | PASS | 0.002 |
| tests.test_providers | test_model_response_dataclass | PASS | 0.002 |
| tests.test_security_regression | test_regression_path_traversal_impossible | PASS | 0.002 |
| tests.test_security_regression | test_regression_same_person_approval_denied | PASS | 0.002 |
| tests.test_security_regression | test_regression_unauthorized_workspace_denied | PASS | 0.002 |
| tests.test_security_regression | test_regression_no_wildcard_cors | PASS | 0.002 |
| tests.test_security_regression | test_regression_zero_external_cloud_endpoints | PASS | 0.009 |

