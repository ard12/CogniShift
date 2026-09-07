import { apiFetch } from "./clients";
import type { Run, RunCreateRequest, RunEvent } from "@/types";

// NOTE: the backend (src/cognishift/app/api/runs.py) exposes exactly:
//   POST   /api/v1/runs
//   GET    /api/v1/runs
//   GET    /api/v1/runs/{run_id}
//   GET    /api/v1/runs/{run_id}/events
//   POST   /api/v1/runs/{run_id}/resume
// There is no cancel endpoint — do not add one here.
const PATHS = {
  list: "/api/v1/runs",
  detail: (id: number) => `/api/v1/runs/${id}`,
  events: (id: number) => `/api/v1/runs/${id}/events`,
  resume: (id: number) => `/api/v1/runs/${id}/resume`,
};

export const runsApi = {
  list: (
    filters: { workspaceId?: number; agentId?: number } = {},
    signal?: AbortSignal
  ) =>
    apiFetch<Run[]>(PATHS.list, {
      query: { workspace_id: filters.workspaceId, agent_id: filters.agentId },
      signal,
    }),

  get: (id: number, signal?: AbortSignal) => apiFetch<Run>(PATHS.detail(id), { signal }),

  events: (id: number, signal?: AbortSignal) =>
    apiFetch<RunEvent[]>(PATHS.events(id), { signal }),

  /**
   * Dispatches a new agent run. This call blocks until the backend engine
   * reaches a terminal or paused state (runs execute synchronously) —
   * there is no separate "queued" state to poll for.
   */
  create: (payload: RunCreateRequest, signal?: AbortSignal): Promise<Run> =>
    apiFetch<Run>(PATHS.list, {
      method: "POST",
      body: {
        workspace_id: payload.workspace_id,
        agent_id: payload.agent_id,
        input_text: payload.input_text,
        input_type: payload.input_image_path ? "multimodal" : payload.input_type ?? "text",
        input_image_path: payload.input_image_path ?? null,
        conversation_history: payload.conversation_history ?? [],
      },
      signal,
    }),

  /** Requires 'supervisor' or 'administrator' role — backend enforces this. */
  resume: (id: number) =>
    apiFetch<Run>(PATHS.resume(id), {
      method: "POST",
    }),
};
