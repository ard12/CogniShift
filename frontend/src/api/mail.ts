import { apiFetch } from "./clients";

export interface MailMessageMetadata {
  id: number;
  alert_type: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  subject: string;
  sender: string;
  recipients: string[];
  composition_mode: string;
  related_user?: string;
  related_ip?: string;
  related_run_id?: number;
  created_at: string;
  is_read: number;
  read_at?: string;
}

export interface MailCitation {
  id: number;
  alert_id: number;
  citation_index: number;
  citation_class: string;
  display_label: string;
  source_id: string;
  page_number?: number;
  validated: number;
  metadata: Record<string, any>;
}

export interface MailMessageDetail extends MailMessageMetadata {
  body_text: string;
  body_html?: string;
  evidence_pack: Record<string, any>;
  citations: MailCitation[];
  eml_path?: string;
  artifact?: {
    id: number;
    filename: string;
    relative_path: string;
    file_size: number;
    sha256_hash: string;
  };
}

export interface MailboxResponse {
  messages: MailMessageMetadata[];
  unread_count: number;
  total_count: number;
  role: string;
  user_id: string;
}

export interface SmtpHealthStatus {
  status: "ACTIVE" | "UNAVAILABLE";
  host: string;
  port: number;
  banner?: string;
  error?: string;
  loopback_only: boolean;
}

export const mailApi = {
  list: (folder?: string, limit?: number, offset?: number) =>
    apiFetch<MailboxResponse>("/api/v1/mail", {
      query: { folder, limit, offset },
    }),
  get: (alertId: number) =>
    apiFetch<MailMessageDetail>(`/api/v1/mail/${alertId}`),
  markRead: (alertId: number) =>
    apiFetch<{ status: string; alert_id: number; user_id: string; is_read: number }>(
      `/api/v1/mail/${alertId}/read`,
      { method: "POST" }
    ),
  dispatchTest: () =>
    apiFetch<{ status: string; alert_id: number; subject: string; delivered: boolean }>(
      "/api/v1/mail/dispatch-test",
      { method: "POST" }
    ),
  clear: () =>
    apiFetch<{ status: string; deleted_count: number }>("/api/v1/mail/clear", {
      method: "POST",
    }),
  smtpHealth: () =>
    apiFetch<SmtpHealthStatus>("/api/v1/mail/smtp-health"),
};
