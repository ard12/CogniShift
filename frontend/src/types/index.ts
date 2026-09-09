/**
 * Shared domain types.
 *
 * These mirror the actual Pydantic response models in
 * `src/cognishift/app/db/models.py` and the literal JSON shapes returned by
 * `src/cognishift/app/main.py` and `src/cognishift/app/api/sovereignty.py`.
 * Field names intentionally match the backend's snake_case wire format.
 */

export type ID = number;

export type IsoDateTime = string;

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export type UserRole = "operator" | "supervisor" | "administrator";

// ---------------------------------------------------------------------------
// Workspaces
// ---------------------------------------------------------------------------

export interface Workspace {
  id: ID;
  name: string;
  description?: string | null;
  operating_mode: string;
  created_at: IsoDateTime;
}

export interface WorkspaceCreateRequest {
  name: string;
  description?: string | null;
  operating_mode?: string;
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

export interface Agent {
  id: ID;
  workspace_id: ID;
  name: string;
  description?: string | null;
  system_instructions?: string | null;
  model_name: string;
  status: string;
  allowed_tool_ids: number[];
  approval_required: boolean;
  knowledge_source_ids: number[];
  created_at: IsoDateTime;
}

export interface AgentCreateRequest {
  workspace_id: ID;
  name: string;
  description?: string | null;
  system_instructions?: string | null;
  model_name?: string;
  allowed_tool_ids?: number[];
  approval_required?: boolean;
  knowledge_source_ids?: number[];
}

export interface AgentUpdateRequest {
  name?: string;
  description?: string | null;
  system_instructions?: string | null;
  model_name?: string;
  allowed_tool_ids?: number[];
  approval_required?: boolean;
  knowledge_source_ids?: number[];
  status?: string;
}

// ---------------------------------------------------------------------------
// Knowledge / documents
// ---------------------------------------------------------------------------

export interface KnowledgeSource {
  id: ID;
  workspace_id: ID;
  name: string;
  source_type: string;
  original_filename?: string | null;
  local_path?: string | null;
  processing_status: string;
  checksum?: string | null;
  chunk_count: number;
  active_processing_version?: string | null;
  created_at: IsoDateTime;
}

export interface DocumentProcessingJob {
  id: ID;
  source_id: ID;
  workspace_id: ID;
  processing_version: string;
  status: string;
  total_pages: number;
  native_pages: number;
  ocr_pages: number;
  vision_pages: number;
  failed_pages: number;
  error_code?: string | null;
  error_message?: string | null;
  started_at: IsoDateTime;
  completed_at?: IsoDateTime | null;
}

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

/** The backend stores these as free-text; these are the values the engine emits. */
export type RunStatus =
  | "running"
  | "resuming"
  | "paused"
  | "completed"
  | "failed"
  | string;

export interface Run {
  id: ID;
  workspace_id: ID;
  agent_id: ID;
  user_id: string;
  input_text?: string | null;
  input_type: string;
  input_image_path?: string | null;
  status: RunStatus;
  model_name?: string | null;
  operating_mode?: string | null;
  result_text?: string | null;
  sources_used?: string | null;
  confidence?: number | null;
  started_at: IsoDateTime;
  completed_at?: IsoDateTime | null;
  error_message?: string | null;
  routing_info?: Record<string, unknown> | null;
  structured_plan?: string | null;
}

export interface PlanStep {
  index: number;
  title: string;
  description?: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  duration_ms?: number;
}

export interface StructuredPlan {
  goal?: string;
  intent?: string;
  steps: PlanStep[];
}

export interface RunEvent {
  id: ID;
  run_id: ID;
  event_type: string;
  message?: string | null;
  structured_data?: string | null;
  created_at: IsoDateTime;
}

export interface RunCreateRequest {
  workspace_id: ID;
  agent_id: ID;
  input_text?: string;
  input_type?: string;
  input_image_path?: string | null;
  conversation_history?: Array<{ role: string; content: string; timestamp?: string }>;
}

export interface RunFlowStage {
  key: string;
  label: string;
  value: string;
  detail?: string | null;
  status: "complete" | "warning" | "unavailable";
}

export interface RunStatusSummary {
  run_id: ID;
  run_status: string;
  stages: RunFlowStage[];
}

// ---------------------------------------------------------------------------
// Approvals
// ---------------------------------------------------------------------------

export type ApprovalStatus = "pending" | "approved" | "rejected" | string;

export interface Approval {
  id: ID;
  run_id: ID;
  tool_id: ID;
  status: ApprovalStatus;
  request_reason?: string | null;
  parameters?: string | null;
  risk_level?: string | null;
  requested_at: IsoDateTime;
  reviewed_by?: string | null;
  reviewed_by_2?: string | null;
  reviewed_at?: IsoDateTime | null;
  reviewed_at_2?: string | null;
  required_approvals?: number;
}

// ---------------------------------------------------------------------------
// Artifacts
// ---------------------------------------------------------------------------

export interface Artifact {
  id: ID;
  workspace_id: ID;
  run_id?: ID | null;
  filename: string;
  relative_path: string;
  artifact_type: string;
  title?: string | null;
  description?: string | null;
  file_size: number;
  sha256_hash: string;
  metadata?: string | null;
  created_at: IsoDateTime;
}

export interface ArtifactListResponse {
  total: number;
  artifacts: Artifact[];
}

// ---------------------------------------------------------------------------
// System / Sovereignty
// ---------------------------------------------------------------------------

export interface OllamaModelInfo {
  name: string;
  model?: string;
  size?: number;
  digest?: string;
  modified_at?: string;
  [key: string]: unknown;
}

export interface SystemStatus {
  operating_mode: string;
  ollama_available: boolean;
  available_models: OllamaModelInfo[];
  database_initialized: boolean;
  version: string;
}

export interface PrivacyStatus {
  operating_mode: string;
  external_apis_blocked: boolean;
  data_directory: string;
}

export interface SovereigntyComponentStatus {
  status: string;
  details?: string | null;
  is_ready: boolean;
}

export interface SovereigntyStatus {
  policy_mode: string;
  sovereignty_enforced: boolean;
  public_egress_allowed: boolean;
  all_components_ready: boolean;
  components: Record<string, SovereigntyComponentStatus>;
  allowed_destinations_count: number;
  total_blocked_attempts: number;
  user_role: UserRole;
}

export type NetworkPolicyDecision = "ALLOWED" | "BLOCKED";

export interface NetworkEvent {
  id: ID;
  timestamp: IsoDateTime;
  component: string;
  method?: string | null;
  requested_host: string;
  resolved_ip?: string | null;
  port?: number | null;
  destination_class: string;
  policy_decision: NetworkPolicyDecision;
  reason: string;
}

export interface NetworkEventsResponse {
  total: number;
  limit: number;
  offset: number;
  events: NetworkEvent[];
}

export interface SecurityDatum {
  status: string;
  label: string;
  evidence?: string | null;
}

export interface SecurityStatus {
  identity: SecurityDatum;
  device: SecurityDatum;
  workspace: SecurityDatum;
  local_ai: SecurityDatum;
  external_internet: SecurityDatum;
  network_interface?: SecurityDatum;
  docker_sandbox?: SecurityDatum;
  sensitive_tools: SecurityDatum;
  audit_logging: SecurityDatum;
  trusted_device_enforcement: boolean;
}
