import { apiFetch } from "./clients";
import type { Approval } from "@/types";

// Adjust these paths if your backend's actual routes differ.
//
// IMPORTANT: this module only calls the backend's existing approval
// endpoints. All approval/rejection validation and security logic lives in
// the backend. This frontend only displays the request and forwards
// the operator's decision.
const PATHS = {
  list: "/api/approvals",
  detail: (id: string) => `/api/approvals/${id}`,
  approve: (id: string) => `/api/approvals/${id}/approve`,
  reject: (id: string) => `/api/approvals/${id}/reject`,
};

export const approvalsApi = {
  list: (signal?: AbortSignal) =>
    apiFetch<Approval[]>(PATHS.list, { signal }),

  get: (id: string, signal?: AbortSignal) =>
    apiFetch<Approval>(PATHS.detail(id), { signal }),

  approve: (id: string, note?: string) =>
    apiFetch<Approval>(PATHS.approve(id), {
      method: "POST",
      body: note ? { note } : undefined,
    }),

  reject: (id: string, note?: string) =>
    apiFetch<Approval>(PATHS.reject(id), {
      method: "POST",
      body: note ? { note } : undefined,
    }),
};