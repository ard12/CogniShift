import { apiFetch } from "./clients";

export const authApi = {
  demoSession: (personaId: string) => apiFetch<{session_token: string; expires_in_seconds: number}>("/api/v1/auth/demo-session", {method: "POST", body: {persona_id: personaId}}),
  challenge: (token: string, body: unknown) => apiFetch<{status: string; challenge_id: string; challenge: string}>("/api/v1/auth/device/challenge", {method: "POST", body, token}),
  verifyDevice: (token: string, body: unknown) => apiFetch<{device_session: string; expires_in_seconds: number; device_status: string}>("/api/v1/auth/device/verify", {method: "POST", body, token}),
};
