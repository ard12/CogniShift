import { apiFetch, buildUrl, authHeader, ApiError } from "./clients";
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
   * bearer token and trusted-device proof attached, then hand the browser a
   * blob URL. A raw navigation cannot carry either required custom header.
   */
  async download(workspaceId: number, artifactId: number, filename: string): Promise<void> {
    const res = await fetch(buildUrl(PATHS.download(workspaceId, artifactId)), {
      headers: authHeader(),
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
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },

  /**
   * Fetches an artifact blob with bearer and device authentication and returns
   * a temporary object URL that can be used as an <img src> or iframe source.
   */
  async getBlobUrl(workspaceId: number, artifactId: number): Promise<string> {
    const res = await fetch(buildUrl(PATHS.download(workspaceId, artifactId)), {
      headers: authHeader(),
    });
    if (!res.ok) {
      throw new ApiError(`Failed to fetch artifact blob (${res.status})`, res.status);
    }
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  },
};
