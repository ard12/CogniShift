import { apiFetch, ApiError } from "./clients";
import { getStoredToken } from "@/lib/token-storage";
import type { Artifact, ArtifactListResponse } from "@/types";

const PATHS = {
  list: (workspaceId: number) => `/api/v1/workspaces/${workspaceId}/artifacts`,
  detail: (workspaceId: number, artifactId: number) =>
    `/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}`,
  download: (workspaceId: number, artifactId: number) =>
    `/api/v1/workspaces/${workspaceId}/artifacts/${artifactId}/download`,
};

export const artifactsApi = {
  list: (workspaceId: number, signal?: AbortSignal) =>
    apiFetch<ArtifactListResponse>(PATHS.list(workspaceId), { signal }),

  get: (workspaceId: number, artifactId: number, signal?: AbortSignal) =>
    apiFetch<Artifact>(PATHS.detail(workspaceId, artifactId), { signal }),

  /**
   * Triggers a browser download of the artifact. The download endpoint is a
   * plain authenticated GET returning a file stream, so we fetch it with the
   * bearer token attached and hand the browser a blob URL rather than
   * navigating directly (a raw <a href> would not carry the Authorization
   * header) or parsing the response as JSON.
   */
  async download(workspaceId: number, artifactId: number, filename: string): Promise<void> {
    const token = getStoredToken();
    const res = await fetch(PATHS.download(workspaceId, artifactId), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      let detail: unknown;
      try {
        detail = await res.json();
      } catch {
        detail = undefined;
      }
      throw new ApiError(`Download failed (${res.status})`, res.status, detail);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
};
