import { apiFetch } from "./clients";
import type { Workspace } from "@/types";

// Adjust these paths if your backend's actual routes differ.
const PATHS = {
  list: "/api/workspaces",
  detail: (id: string) => `/api/workspaces/${id}`,
};

export const workspacesApi = {
  list: (signal?: AbortSignal) =>
    apiFetch<Workspace[]>(PATHS.list, { signal }),

  get: (id: string, signal?: AbortSignal) =>
    apiFetch<Workspace>(PATHS.detail(id), { signal }),
};