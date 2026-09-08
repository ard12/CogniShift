import { apiFetch } from "./clients";

export interface TemporaryPermit {
  id: number;
  permit_code: string;
  workspace_id: number;
  user_id: string;
  trusted_device_id?: string;
  action: string;
  resource: string;
  max_uses: number;
  uses: number;
  valid_from: string;
  expires_at: string;
  status: "PENDING_APPROVAL" | "ACTIVE" | "CONSUMED" | "EXPIRED" | "REVOKED";
  requested_by: string;
  first_approver?: string;
  first_approved_at?: string;
  second_approver?: string;
  second_approved_at?: string;
  admin_override: number;
  consumed_at?: string;
  artifact_id?: number;
  created_at: string;
  artifact?: {
    id: number;
    filename: string;
    relative_path: string;
    file_size: number;
    sha256_hash: string;
  };
  audit_events?: Array<{
    id: number;
    action: string;
    actor_id: string;
    created_at: string;
    details: string;
    result: string;
  }>;
}

export interface CreatePermitPayload {
  workspace_id: number;
  action?: string;
  resource?: string;
  valid_duration_minutes?: number;
  target_user_id?: string;
  trusted_device_id?: string;
  reason?: string;
}

export interface ExecutePermitPayload {
  permit_code: string;
  action?: string;
  resource?: string;
  parameters?: Record<string, unknown>;
}

export interface ExecutionResult {
  status: string;
  permit_code: string;
  user_id: string;
  resource: string;
  action: string;
  uses: number;
  max_uses: number;
  remaining_uses: number;
  consumed_at?: string;
  simulated_result: string;
  latency_ms: number;
  disclaimer: string;
}

export const authorizationsApi = {
  create: (payload: CreatePermitPayload) =>
    apiFetch<TemporaryPermit>("/api/v1/authorizations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  list: (workspaceId?: number, statusFilter?: string) =>
    apiFetch<{ permits: TemporaryPermit[]; total: number }>("/api/v1/authorizations", {
      query: { workspace_id: workspaceId, status_filter: statusFilter },
    }),
  get: (permitId: number) =>
    apiFetch<TemporaryPermit>(`/api/v1/authorizations/${permitId}`),
  approve: (permitId: number) =>
    apiFetch<TemporaryPermit & { approval_stage: string; latency_ms: number }>(
      `/api/v1/authorizations/${permitId}/approve`,
      { method: "POST" }
    ),
  adminOverride: (permitId: number, justification: string) =>
    apiFetch<TemporaryPermit>(`/api/v1/authorizations/${permitId}/admin-override`, {
      method: "POST",
      body: JSON.stringify({ justification }),
    }),
  revoke: (permitId: number, reason?: string) =>
    apiFetch<TemporaryPermit>(`/api/v1/authorizations/${permitId}/revoke`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  execute: (payload: ExecutePermitPayload) =>
    apiFetch<ExecutionResult>("/api/v1/authorizations/execute", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
