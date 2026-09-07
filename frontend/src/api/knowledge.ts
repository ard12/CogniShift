import { apiFetch, apiUpload } from "./clients";
import type { DocumentProcessingJob, KnowledgeSource } from "@/types";

// NOTE: the backend (src/cognishift/app/api/knowledge.py) does not expose a
// standalone knowledge-search endpoint. Retrieval happens internally during
// agent runs (see src/cognishift/core/retriever.py). Do not add a `search`
// method here — there is nothing to call.
const PATHS = {
  list: "/api/v1/knowledge",
  upload: "/api/v1/knowledge/upload",
  detail: (id: number) => `/api/v1/knowledge/${id}`,
  jobs: (id: number) => `/api/v1/knowledge/${id}/jobs`,
};

export const knowledgeApi = {
  list: (workspaceId: number, signal?: AbortSignal) =>
    apiFetch<KnowledgeSource[]>(PATHS.list, {
      query: { workspace_id: workspaceId },
      signal,
    }),

  get: (id: number, signal?: AbortSignal) => apiFetch<KnowledgeSource>(PATHS.detail(id), { signal }),

  /** Accepts .pdf, .png, .jpg/.jpeg, .xlsx, .xls, and .csv files. */
  upload: (file: File, workspaceId: number, signal?: AbortSignal) => {
    const formData = new FormData();
    formData.append("workspace_id", String(workspaceId));
    formData.append("file", file);

    return apiUpload<KnowledgeSource>(PATHS.upload, formData, { signal });
  },

  remove: (id: number) =>
    apiFetch<{ status: string; source_id: number; message: string }>(PATHS.detail(id), {
      method: "DELETE",
    }),

  jobs: (id: number, signal?: AbortSignal) =>
    apiFetch<DocumentProcessingJob[]>(PATHS.jobs(id), { signal }),
};