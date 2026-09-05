/**
 * Central API client.
 *
 * Every request the frontend makes goes through `apiFetch` below, so there
 * is exactly one place that knows how to reach the backend, attach headers,
 * and turn a non-2xx response into a typed error. Feature modules in this
 * `api/` folder (workspaces.ts, runs.ts, ...) should never call `fetch`
 * directly — they call `apiFetch`/`apiUpload` and stay focused on paths and
 * types.
 *
 * Base URL:
 * - In production, the frontend is built and copied into the FastAPI
 *   static directory, so relative paths ("/api/...") already resolve to
 *   the right place — BASE_URL is left empty.
 * - In development, set VITE_API_BASE_URL if your backend isn't at the
 *   default proxied address (see vite.config.ts).
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorBody(res: Response): Promise<{ message: string; detail?: unknown }> {
  try {
    const body = await res.json();
    // FastAPI validation/HTTPException errors commonly use `detail`.
    const detail = body?.detail ?? body;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
        ? detail.map((d) => d?.msg ?? JSON.stringify(d)).join("; ")
        : `Request failed (${res.status})`;
    return { message, detail };
  } catch {
    return { message: `Request failed (${res.status})` };
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const { message, detail } = await parseErrorBody(res);
    throw new ApiError(message, res.status, detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return undefined as T;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(BASE_URL + path, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  // Use a relative URL when BASE_URL is empty, so the app works no matter
  // what path the static files are mounted under.
  return BASE_URL ? url.toString() : url.pathname + url.search;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, signal } = options;

  const res = await fetch(buildUrl(path, query), {
    method,
    signal,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  return handleResponse<T>(res);
}

/** For endpoints that accept multipart/form-data (file uploads, images). */
export async function apiUpload<T>(
  path: string,
  formData: FormData,
  options: { method?: "POST" | "PUT"; signal?: AbortSignal } = {}
): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: options.method ?? "POST",
    body: formData,
    signal: options.signal,
    // No Content-Type header — the browser sets the multipart boundary.
  });

  return handleResponse<T>(res);
}