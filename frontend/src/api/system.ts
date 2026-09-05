import { apiFetch } from "./clients";
import type { SystemStatus } from "@/types";

// Adjust this path if your backend's actual route differs.
const PATHS = {
  status: "/api/system/status",
};

export const systemApi = {
  status: (signal?: AbortSignal) =>
    apiFetch<SystemStatus>(PATHS.status, { signal }),
};