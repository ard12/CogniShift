import { apiFetch } from "./clients";
import type { Workspace, WorkspaceCreateRequest } from "@/types";

const PATHS = {
  list: "/api/v1/workspaces",
  detail: (id: number) => `/api/v1/workspaces/${id}`,
};

export const workspacesApi = {
  list: (signal?: AbortSignal) => apiFetch<Workspace[]>(PATHS.list, { signal }),

  get: (id: number, signal?: AbortSignal) => apiFetch<Workspace>(PATHS.detail(id), { signal }),

  /** Requires 'supervisor' or 'administrator' role — backend enforces this. */
  create: (payload: WorkspaceCreateRequest) =>
    apiFetch<Workspace>(PATHS.list, {
      method: "POST",
      body: payload,
    }),
};