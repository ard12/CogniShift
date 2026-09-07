import { apiFetch } from "./clients";
import type { Agent, AgentCreateRequest, AgentUpdateRequest } from "@/types";

const PATHS = {
  list: "/api/v1/agents",
  detail: (id: number) => `/api/v1/agents/${id}`,
};

export const agentsApi = {
  /** Pass workspaceId to scope to a single workspace's agent definitions. */
  list: (workspaceId?: number, signal?: AbortSignal) =>
    apiFetch<Agent[]>(PATHS.list, {
      query: { workspace_id: workspaceId },
      signal,
    }),

  get: (id: number, signal?: AbortSignal) => apiFetch<Agent>(PATHS.detail(id), { signal }),

  create: (payload: AgentCreateRequest) =>
    apiFetch<Agent>(PATHS.list, {
      method: "POST",
      body: payload,
    }),

  update: (id: number, payload: AgentUpdateRequest) =>
    apiFetch<Agent>(PATHS.detail(id), {
      method: "PATCH",
      body: payload,
    }),
};