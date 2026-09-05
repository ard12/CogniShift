import { apiFetch } from "./clients";
import type { Agent } from "@/types";

// Adjust these paths if your backend's actual routes differ.
const PATHS = {
  list: "/api/agents",
  detail: (id: string) => `/api/agents/${id}`,
};

export const agentsApi = {
  /** Pass workspaceId to scope to a single workspace's agent definitions. */
  list: (workspaceId?: string, signal?: AbortSignal) =>
    apiFetch<Agent[]>(PATHS.list, {
      query: { workspace_id: workspaceId },
      signal,
    }),

  get: (id: string, signal?: AbortSignal) =>
    apiFetch<Agent>(PATHS.detail(id), { signal }),
};