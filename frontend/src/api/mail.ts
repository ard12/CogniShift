import { apiFetch, apiUpload, buildUrl, authHeader, ApiError } from "./clients";
import { getStoredToken } from "@/lib/token-storage";
import { getDeviceSession } from "@/lib/device-identity";

export interface MailAttachment {
  id: number;
  filename: string;
  content_type: string;
  file_size: number;
  sha256_hash: string;
}

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
  metadata: Record<string, unknown>;
}

export interface MailEvidencePack {
  permit_code?: string;
  tool_name?: string;
  [key: string]: unknown;
}

export interface MailMessageDetail extends MailMessageMetadata {
  body_text: string;
  body_html?: string;
  evidence_pack: MailEvidencePack;
  citations: MailCitation[];
  attachments?: MailAttachment[];
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

export interface MailRecipient {
  user_id: string;
  display_name: string;
  role: string;
  internal_email: string;
}

export interface SendMailPayload {
  recipients: string[];
  subject: string;
  body_text: string;
  body_html?: string;
  attachment_ids?: number[];
}

export interface DraftAssistResponse {
  subject: string;
  body: string;
  model: string;
  latency_ms: number;
  fallback: boolean;
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
  recipients: () =>
    apiFetch<MailRecipient[]>("/api/v1/mail/recipients"),
  send: (payload: SendMailPayload) =>
    apiFetch<{ status: string; alert_id: number; recipients: string[]; created_at: string }>(
      "/api/v1/mail/send",
      { method: "POST", body: payload }
    ),
  uploadAttachment: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiUpload<{ id: number; filename: string; file_size: number; content_type: string; sha256: string }>(
      "/api/v1/mail/attachments/upload",
      formData
    );
  },
  downloadAttachmentUrl: (alertId: number, attachmentId: number) =>
    `/api/v1/mail/${alertId}/attachments/${attachmentId}`,
  async downloadAttachment(alertId: number, attachmentId: number, filename: string): Promise<void> {
    const token = getStoredToken();
    const deviceSession = getDeviceSession();
    const res = await fetch(buildUrl(`/api/v1/mail/${alertId}/attachments/${attachmentId}`), {
      headers: {
        ...authHeader(token ?? undefined),
        ...(deviceSession ? { "X-Device-Session": deviceSession } : {}),
      },
    });
    if (!res.ok) {
      let detail: unknown;
      try {
        detail = await res.json();
      } catch {
        detail = undefined;
      }
      throw new ApiError(`Attachment download failed (${res.status})`, res.status, detail);
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
  draftAssist: (intent: string, context?: string, tone?: string) =>
    apiFetch<DraftAssistResponse>("/api/v1/mail/draft/assist", {
      method: "POST",
      body: { intent, context, tone },
    }),
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
