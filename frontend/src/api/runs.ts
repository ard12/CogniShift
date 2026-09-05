import { apiFetch, apiUpload } from "./clients";
import type { NewRunPayload, Run, RunEvent } from "@/types";

// Adjust these paths if your backend's actual routes differ.
const PATHS = {
  list: "/api/runs",
  detail: (id: string) => `/api/runs/${id}`,
  events: (id: string) => `/api/runs/${id}/events`,
  cancel: (id: string) => `/api/runs/${id}/cancel`,
};

export const runsApi = {
  list: (signal?: AbortSignal) =>
    apiFetch<Run[]>(PATHS.list, { signal }),

  get: (id: string, signal?: AbortSignal) =>
    apiFetch<Run>(PATHS.detail(id), { signal }),

  events: (id: string, signal?: AbortSignal) =>
    apiFetch<RunEvent[]>(PATHS.events(id), { signal }),

  /**
   * Starts a new agent run.
   * Uses multipart/form-data when an image is attached.
   * Otherwise sends normal JSON.
   */
  create: (
    payload: NewRunPayload,
    signal?: AbortSignal
  ): Promise<Run> => {
    if (payload.image) {
      const formData = new FormData();

      formData.append("workspace_id", payload.workspace_id);
      formData.append("agent_id", payload.agent_id);
      formData.append("query", payload.query);
      formData.append("image", payload.image);

      return apiUpload<Run>(
        PATHS.list,
        formData,
        { signal }
      );
    }

    return apiFetch<Run>(PATHS.list, {
      method: "POST",
      body: {
        workspace_id: payload.workspace_id,
        agent_id: payload.agent_id,
        query: payload.query,
      },
      signal,
    });
  },

  cancel: (id: string) =>
    apiFetch<Run>(PATHS.cancel(id), {
      method: "POST",
    }),
};