import { apiFetch } from "./clients";
import type { SecurityStatus } from "@/types";

export interface PendingDevice { device_id: string; user_id: string; display_name: string; key_fingerprint: string; created_at: string }

export const securityApi = {
  status: (workspaceId: number) => apiFetch<SecurityStatus>("/api/v1/security/status", {query: {workspace_id: workspaceId}}),
  pendingDevices: () => apiFetch<PendingDevice[]>("/api/v1/security/devices/pending"),
  approveDevice: (deviceId: string) => apiFetch<{status: string; device_id: string}>(`/api/v1/security/devices/${encodeURIComponent(deviceId)}/approve`, {method: "POST"}),
};
