import { apiFetch } from "./clients";
import type { SecurityStatus } from "@/types";

export interface PendingDevice {
  device_id: string;
  user_id: string;
  display_name: string;
  key_fingerprint: string;
  last_ip?: string;
  created_at: string;
}

export interface DeviceRecord {
  id: number;
  device_id: string;
  user_id: string;
  display_name: string;
  key_fingerprint: string;
  status: "approved" | "pending" | "revoked" | "blocked";
  approved_by?: string;
  approved_at?: string;
  last_verified_at?: string;
  last_ip?: string;
  previous_ip?: string;
  created_at: string;
}

export interface SecurityAlert {
  id: number;
  alert_type: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  subject: string;
  sender: string;
  recipients: string[];
  related_user?: string;
  related_ip?: string;
  related_device_id?: string;
  related_run_id?: number;
  is_read: number;
  composition_mode: string;
  created_at: string;
}

export interface SecurityAlertCitation {
  id: number;
  alert_id: number;
  citation_index: number;
  citation_class: string;
  display_label: string;
  source_id: string;
  page_number?: number;
  validated: number;
  metadata: Record<string, any>;
}

export interface SecurityAlertDetail extends SecurityAlert {
  body_text: string;
  body_html?: string;
  evidence_pack: Record<string, any>;
  citations: SecurityAlertCitation[];
}

export interface MailboxResponse {
  alerts: SecurityAlert[];
  unread_count: number;
  total_count: number;
}

export interface SmtpHealthStatus {
  status: "ACTIVE" | "UNAVAILABLE";
  host: string;
  port: number;
  banner?: string;
  error?: string;
  loopback_only: boolean;
}

export const securityApi = {
  status: (workspaceId: number) => apiFetch<SecurityStatus>("/api/v1/security/status", {query: {workspace_id: workspaceId}}),
  pendingDevices: () => apiFetch<PendingDevice[]>("/api/v1/security/devices/pending"),
  listDevices: () => apiFetch<DeviceRecord[]>("/api/v1/security/devices"),
  approveDevice: (deviceId: string, userId: string) => apiFetch<{status: string; device_id: string; user_id: string}>(`/api/v1/security/devices/${encodeURIComponent(deviceId)}/approve`, {method: "POST", query: {user_id: userId}}),
  revokeDevice: (deviceId: string, userId?: string) => apiFetch<{status: string; device_id: string}>(`/api/v1/security/devices/${encodeURIComponent(deviceId)}/revoke`, {method: "POST", query: userId ? {user_id: userId} : undefined}),
  blockDevice: (deviceId: string, userId?: string) => apiFetch<{status: string; device_id: string}>(`/api/v1/security/devices/${encodeURIComponent(deviceId)}/block`, {method: "POST", query: userId ? {user_id: userId} : undefined}),
  mailbox: (limit?: number, offset?: number) => apiFetch<MailboxResponse>("/api/v1/security/alerts/mailbox", {query: {limit, offset}}),
  alertDetail: (alertId: number) => apiFetch<SecurityAlertDetail>(`/api/v1/security/alerts/${alertId}`),
  markAlertRead: (alertId: number) => apiFetch<{status: string; id: number}>(`/api/v1/security/alerts/${alertId}/read`, {method: "POST"}),
  clearMailbox: () => apiFetch<{status: string; deleted_count: number}>("/api/v1/security/alerts/clear", {method: "POST"}),
  smtpHealth: () => apiFetch<SmtpHealthStatus>("/api/v1/security/alerts/smtp-health"),
  dispatchTestAlert: () => apiFetch<{status: string; alert_id: number; subject: string; delivered: boolean}>("/api/v1/security/alerts/dispatch-test", {method: "POST"}),
};
