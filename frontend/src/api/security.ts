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
  created_at: string;
}

export const securityApi = {
  status: (workspaceId: number) => apiFetch<SecurityStatus>("/api/v1/security/status", {query: {workspace_id: workspaceId}}),
  pendingDevices: () => apiFetch<PendingDevice[]>("/api/v1/security/devices/pending"),
  listDevices: () => apiFetch<DeviceRecord[]>("/api/v1/security/devices"),
  approveDevice: (deviceId: string, userId: string) => apiFetch<{status: string; device_id: string; user_id: string}>(`/api/v1/security/devices/${encodeURIComponent(deviceId)}/approve`, {method: "POST", query: {user_id: userId}}),
  revokeDevice: (deviceId: string, userId?: string) => apiFetch<{status: string; device_id: string}>(`/api/v1/security/devices/${encodeURIComponent(deviceId)}/revoke`, {method: "POST", query: userId ? {user_id: userId} : undefined}),
  blockDevice: (deviceId: string, userId?: string) => apiFetch<{status: string; device_id: string}>(`/api/v1/security/devices/${encodeURIComponent(deviceId)}/block`, {method: "POST", query: userId ? {user_id: userId} : undefined}),
};
