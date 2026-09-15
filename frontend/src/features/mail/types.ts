export type FolderType = "all" | "sent" | "permits" | "security" | "governance";

export type {
  MailMessageMetadata,
  MailMessageDetail,
  SmtpHealthStatus,
  MailRecipient,
  MailAttachment,
  SendMailPayload,
  DraftAssistResponse,
} from "@/api/mail";

export type { ExecutionResult, CreatePermitPayload } from "@/api/authorizations";
