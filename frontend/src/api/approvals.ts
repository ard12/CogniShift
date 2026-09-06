import { apiFetch } from "./clients";
import type { Approval } from "@/types";

// NOTE: the backend (src/cognishift/app/api/approvals.py) has no approval
// detail endpoint and no generic list-all — only the pending queue. Approving
// or rejecting a request also triggers the engine to resume the associated
// run server-side, so the frontend does not need to call runs.resume itself
// afterward.
const PATHS = {
  listPending: "/api/v1/approvals",
  approve: (id: number) => `/api/v1/approvals/${id}/approve`,
  reject: (id: number) => `/api/v1/approvals/${id}/reject`,
};

export const approvalsApi = {
  listPending: (signal?: AbortSignal) => apiFetch<Approval[]>(PATHS.listPending, { signal }),

  /**
   * Enforces the Four-Eyes policy server-side: the approver must be a
   * 'supervisor' or 'administrator', and cannot be the run's original
   * requester. Surfacing the resulting 403 honestly is the frontend's job.
   */
  approve: (id: number) =>
    apiFetch<Approval>(PATHS.approve(id), {
      method: "POST",
    }),

  reject: (id: number) =>
    apiFetch<Approval>(PATHS.reject(id), {
      method: "POST",
    }),
};
