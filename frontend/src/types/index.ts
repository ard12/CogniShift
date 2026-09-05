/**
 * Shared domain types.
 *
 * These describe the shapes the console expects back from the FastAPI
 * backend. They're written defensively (lots of optional fields) because
 * the exact backend response shape wasn't available while building this
 * frontend — see README.md "Connecting to your backend". Adjust these to
 * match your actual Pydantic response models; the rest of the app only
 * depends on these types, not on raw API responses, so this is the one
 * place you should need to edit.
 */

export type ID = string;

export type IsoDateTime = string;

// ---------------------------------------------------------------------------
// Workspaces
// ---------------------------------------------------------------------------

export interface Workspace {
  id: ID;
  name: string;
  description?: string | null;
  created_at?: IsoDateTime;
  updated_at?: IsoDateTime;
  document_count?: number;
  agent_count?: number;
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

export interface Agent {
  id: ID;
  workspace_id: ID;
  name: string;
  description?: string | null;
  role?: string | null;
  model?: string | null;
  supports_vision?: boolean;
}

// ---------------------------------------------------------------------------
// Knowledge / documents
// ---------------------------------------------------------------------------

export type DocumentStatus = "processing" | "ready" | "failed" | "queued";

export interface KnowledgeDocument {
  id: ID;
  workspace_id: ID;
  filename: string;
  status: DocumentStatus;
  size_bytes?: number;
  page_count?: number;
  uploaded_at?: IsoDateTime;
  error_message?: string | null;
}

export interface SearchResult {
  id: ID;
  title: string;
  content_preview: string;
  source_filename: string;
  page?: number | null;
  score?: number | null;
}

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

export type RunStatus =
  | "queued"
  | "running"
  | "waiting_for_approval"
  | "completed"
  | "failed"
  | "cancelled";

export interface Run {
  id: ID;
  workspace_id: ID;
  agent_id: ID;
  agent_name?: string;
  workspace_name?: string;
  status: RunStatus;
  query: string;
  result?: string | null;
  has_image?: boolean;
  created_at: IsoDateTime;
  updated_at?: IsoDateTime;
  completed_at?: IsoDateTime | null;
  error_message?: string | null;
}

export type RunEventType =
  | "started"
  | "step"
  | "tool_call"
  | "tool_result"
  | "vision"
  | "approval_requested"
  | "approval_resolved"
  | "completed"
  | "failed"
  | "info";

export interface RunEvent {
  id: ID;
  run_id: ID;
  type: RunEventType;
  message: string;
  timestamp: IsoDateTime;
  data?: Record<string, unknown> | null;
}

export interface NewRunPayload {
  workspace_id: ID;
  agent_id: ID;
  query: string;
  image?: File | null;
}

// ---------------------------------------------------------------------------
// Approvals
// ---------------------------------------------------------------------------

export type ApprovalStatus = "pending" | "approved" | "rejected";

export interface Approval {
  id: ID;
  run_id: ID;
  workspace_name?: string;
  agent_name?: string;
  action: string;
  reason?: string | null;
  context?: string | null;
  status: ApprovalStatus;
  created_at: IsoDateTime;
  resolved_at?: IsoDateTime | null;
  resolved_by?: string | null;
}

// ---------------------------------------------------------------------------
// System
// ---------------------------------------------------------------------------

export type ServiceState = "online" | "degraded" | "offline" | "unknown";

export interface ModelStatus {
  name: string;
  kind?: "text" | "vision" | "embedding" | string;
  available: boolean;
}

export interface SystemStatus {
  backend: ServiceState;
  ollama: ServiceState;
  models: ModelStatus[];
  version?: string;
  uptime_seconds?: number;
  network_mode?: string; // e.g. "local-only"
}