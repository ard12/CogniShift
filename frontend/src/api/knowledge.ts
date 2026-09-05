import { apiFetch, apiUpload } from "./clients";
import type { KnowledgeDocument, SearchResult } from "@/types";

// Adjust these paths if your backend's actual routes differ.
const PATHS = {
  list: "/api/knowledge",
  upload: "/api/knowledge/upload",
  search: "/api/knowledge/search",
  delete: (id: string) => `/api/knowledge/${id}`,
};

export const knowledgeApi = {
  list: (workspaceId?: string, signal?: AbortSignal) =>
    apiFetch<KnowledgeDocument[]>(PATHS.list, {
      query: { workspace_id: workspaceId },
      signal,
    }),

  upload: (file: File, workspaceId: string, signal?: AbortSignal) => {
    const formData = new FormData();

    formData.append("file", file);
    formData.append("workspace_id", workspaceId);

    return apiUpload<KnowledgeDocument>(
      PATHS.upload,
      formData,
      { signal }
    );
  },

  search: (
    query: string,
    workspaceId?: string,
    signal?: AbortSignal
  ) =>
    apiFetch<SearchResult[]>(PATHS.search, {
      query: {
        q: query,
        workspace_id: workspaceId,
      },
      signal,
    }),

  remove: (id: string) =>
    apiFetch<void>(PATHS.delete(id), {
      method: "DELETE",
    }),
};