import { apiFetch } from "./clients";
import type {
  NetworkEventsResponse,
  NetworkPolicyDecision,
  OllamaModelInfo,
  PrivacyStatus,
  SovereigntyStatus,
  SystemStatus,
} from "@/types";

const PATHS = {
  status: "/api/v1/system/status",
  privacyStatus: "/api/v1/system/privacy-status",
  models: "/api/v1/system/models",
  sovereignty: "/api/v1/system/sovereignty",
  networkEvents: "/api/v1/system/network-events",
};

export const systemApi = {
  /** Unauthenticated per src/cognishift/app/main.py. */
  status: (signal?: AbortSignal) => apiFetch<SystemStatus>(PATHS.status, { signal }),

  /** Unauthenticated per src/cognishift/app/main.py. */
  privacyStatus: (signal?: AbortSignal) => apiFetch<PrivacyStatus>(PATHS.privacyStatus, { signal }),

  /** Unauthenticated per src/cognishift/app/main.py. */
  models: (signal?: AbortSignal) => apiFetch<OllamaModelInfo[]>(PATHS.models, { signal }),

  /**
   * Authenticated (src/cognishift/app/api/sovereignty.py). Accepts an
   * explicit token so AuthContext can verify a credential before it has
   * been persisted to storage.
   */
  sovereignty: (token?: string, signal?: AbortSignal) =>
    apiFetch<SovereigntyStatus>(PATHS.sovereignty, { token, signal }),

  networkEvents: (
    filters: { limit?: number; offset?: number; decision?: NetworkPolicyDecision } = {},
    signal?: AbortSignal
  ) =>
    apiFetch<NetworkEventsResponse>(PATHS.networkEvents, {
      query: {
        limit: filters.limit,
        offset: filters.offset,
        decision: filters.decision,
      },
      signal,
    }),
};
