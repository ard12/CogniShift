import { useCallback, useEffect, useState, useRef } from "react";
import {
  mailApi,
  type MailMessageMetadata,
  type MailMessageDetail,
  type SmtpHealthStatus,
  type MailRecipient,
  type MailAttachment,
} from "@/api/mail";
import { buildUrl } from "@/api/clients";
import { securityApi } from "@/api/security";
import { authorizationsApi, type ExecutionResult } from "@/api/authorizations";
import { useAuth } from "@/auth/useAuth";
import { useWorkspaces } from "@/context/useWorkspaces";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import {
  IconAlertTriangle,
  IconCheck,
  IconDownload,
  IconInbox,
  IconLoader,
  IconMail,
  IconPlay,
  IconRefresh,
  IconShieldCheck,
  IconTrash,
} from "@/components/ui/Icon";
import { formatRelativeTime, formatFullDateTime, formatIstTime } from "@/lib/format";
import { getStoredToken } from "@/lib/token-storage";
import { getDeviceSession } from "@/lib/device-identity";

type FolderType = "all" | "sent" | "permits" | "security" | "governance";

export function MailPage() {
  const { role } = useAuth();
  const { selectedWorkspaceId } = useWorkspaces();
  const [messages, setMessages] = useState<MailMessageMetadata[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [currentUserId, setCurrentUserId] = useState<string>("");
  const [selectedFolder, setSelectedFolder] = useState<FolderType>("all");
  const [filterUnreadOnly, setFilterUnreadOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [selectedMessageId, setSelectedMessageId] = useState<number | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<MailMessageDetail | null>(null);
  const [bodyViewMode, setBodyViewMode] = useState<"html" | "text">("html");

  const [smtpHealth, setSmtpHealth] = useState<SmtpHealthStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isDispatching, setIsDispatching] = useState<boolean>(false);

  // Permit Execution State
  const [isExecutingPermit, setIsExecutingPermit] = useState<boolean>(false);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);

  // Request Permit Modal
  const [showRequestModal, setShowRequestModal] = useState<boolean>(false);
  const [requestAction, setRequestAction] = useState<string>("operate_pump");
  const [requestResource, setRequestResource] = useState<string>("P-101A");
  const [requestDuration, setRequestDuration] = useState<number>(60);
  const [requestReason, setRequestReason] = useState<string>("Scheduled operational run under supervisor authorization");
  const [isSubmittingRequest, setIsSubmittingRequest] = useState<boolean>(false);

  // User-to-User Compose Modal State
  const [showComposeModal, setShowComposeModal] = useState<boolean>(false);
  const [availableRecipients, setAvailableRecipients] = useState<MailRecipient[]>([]);
  const [selectedRecipients, setSelectedRecipients] = useState<string[]>([]);
  const [recipientFilter, setRecipientFilter] = useState<string>("");
  const [composeSubject, setComposeSubject] = useState<string>("");
  const [composeBody, setComposeBody] = useState<string>("");
  const [composeAttachments, setComposeAttachments] = useState<MailAttachment[]>([]);
  const [isUploadingAttachment, setIsUploadingAttachment] = useState<boolean>(false);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [isSendingMail, setIsSendingMail] = useState<boolean>(false);
  const [sendError, setSendError] = useState<string | null>(null);

  // Local AI Draft Assist State
  const [showAiAssist, setShowAiAssist] = useState<boolean>(false);
  const [aiIntent, setAiIntent] = useState<string>("");
  const [isGeneratingAiDraft, setIsGeneratingAiDraft] = useState<boolean>(false);
  const [aiDraftStatus, setAiDraftStatus] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const fetchMail = useCallback(async () => {
    try {
      const folderParam = selectedFolder === "all" ? undefined : selectedFolder;
      try {
        const res = await mailApi.list(folderParam, 100, 0);
        setMessages(res.messages);
        setUnreadCount(res.unread_count);
        setTotalCount(res.total_count);
        setCurrentUserId(res.user_id);
        setFetchError(null);
      } catch (err) {
        if (role === "administrator") {
          console.warn("mailApi.list failed, falling back to securityApi.mailbox:", err);
          const mb = await securityApi.mailbox(100, 0);
          setMessages(mb.alerts as unknown as MailMessageMetadata[]);
          setUnreadCount(mb.unread_count);
          setTotalCount(mb.total_count);
          setFetchError(null);
        } else {
          throw err;
        }
      }
      try {
        setSmtpHealth(await mailApi.smtpHealth());
      } catch {
        if (role === "administrator") {
          try {
            setSmtpHealth(await securityApi.smtpHealth());
          } catch {
            // Ignore SMTP health poll fail
          }
        }
      }
    } catch (err) {
      console.error("Mailbox fetch failed:", err);
      setFetchError(err instanceof Error ? err.message : "Mailbox unavailable");
    } finally {
      setIsLoading(false);
    }
  }, [selectedFolder]);

  useEffect(() => {
    void fetchMail();
    const interval = setInterval(() => {
      void fetchMail();
    }, 3000);
    return () => clearInterval(interval);
  }, [fetchMail]);

  // Real-Time Server-Sent Events (SSE) Stream with Disconnect Safety and Auto-Reconnect
  useEffect(() => {
    let active = true;
    let retryTimeout: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();

    async function streamEvents() {
      while (active) {
        try {
          const token = getStoredToken();
          const deviceSession = getDeviceSession();
          const deviceId = typeof window !== "undefined" ? window.localStorage.getItem("cognishift_device_id") : null;
          const headers: Record<string, string> = {};
          if (token) headers["Authorization"] = `Bearer ${token}`;
          if (deviceSession) headers["X-Device-Session"] = deviceSession;
          if (deviceId) headers["X-Device-ID"] = deviceId;

          const response = await fetch(buildUrl("/api/v1/mail/events"), {
            headers,
            signal: controller.signal,
          });

          if (!response.ok || !response.body) {
            await new Promise((resolve) => {
              retryTimeout = setTimeout(resolve, 5000);
            });
            continue;
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (active) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop() ?? "";
            for (const part of parts) {
              if (part.includes("event: new_mail")) {
                void fetchMail();
              }
            }
          }
        } catch (err: unknown) {
          if (active && (!(err instanceof Error) || err.name !== "AbortError")) {
            await new Promise((resolve) => {
              retryTimeout = setTimeout(resolve, 5000);
            });
          }
        }
      }
    }

    void streamEvents();

    return () => {
      active = false;
      controller.abort();
      if (retryTimeout) clearTimeout(retryTimeout);
    };
  }, [fetchMail]);

  const openComposeModal = async () => {
    setShowComposeModal(true);
    setSendError(null);
    setAttachmentError(null);
    try {
      const recs = await mailApi.recipients();
      setAvailableRecipients(recs);
    } catch (err) {
      console.error("Failed to load recipients:", err);
    }
  };

  const handleAttachmentUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];

    const allowed = [".pdf", ".docx", ".xlsx", ".csv", ".txt", ".png", ".jpg", ".jpeg"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!allowed.includes(ext)) {
      setAttachmentError(`File extension '${ext}' is not permitted. Allowed: ${allowed.join(", ")}`);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setAttachmentError("File size exceeds 10 MB limit.");
      return;
    }

    setIsUploadingAttachment(true);
    setAttachmentError(null);

    try {
      const uploaded = await mailApi.uploadAttachment(file);
      setComposeAttachments((prev) => [
        ...prev,
        {
          id: uploaded.id,
          filename: uploaded.filename,
          file_size: uploaded.file_size,
          content_type: uploaded.content_type,
          sha256_hash: uploaded.sha256,
        },
      ]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err: unknown) {
      setAttachmentError(err instanceof Error ? err.message : "Failed to upload attachment.");
    } finally {
      setIsUploadingAttachment(false);
    }
  };

  const removeAttachment = (attId: number) => {
    setComposeAttachments((prev) => prev.filter((a) => a.id !== attId));
  };

  const handleGenerateAiDraft = async () => {
    if (!aiIntent.trim()) return;
    setIsGeneratingAiDraft(true);
    setAiDraftStatus(null);
    try {
      const draft = await mailApi.draftAssist(aiIntent.trim());
      setComposeSubject(draft.subject);
      setComposeBody(draft.body);
      setAiDraftStatus(
        draft.fallback
          ? `Local model unavailable; deterministic fallback used in ${draft.latency_ms}ms`
          : `Draft generated via local ${draft.model} in ${draft.latency_ms}ms`
      );
      setShowAiAssist(false);
    } catch (err: unknown) {
      setAiDraftStatus(err instanceof Error ? err.message : "AI drafting failed.");
    } finally {
      setIsGeneratingAiDraft(false);
    }
  };

  const handleSendMail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedRecipients.length === 0) {
      setSendError("Please select at least one recipient.");
      return;
    }
    if (!composeSubject.trim()) {
      setSendError("Please enter a subject.");
      return;
    }
    if (!composeBody.trim()) {
      setSendError("Please enter a message body.");
      return;
    }

    setIsSendingMail(true);
    setSendError(null);

    try {
      const res = await mailApi.send({
        recipients: selectedRecipients,
        subject: composeSubject.trim(),
        body_text: composeBody.trim(),
        attachment_ids: composeAttachments.map((a) => a.id),
      });

      setShowComposeModal(false);
      setSelectedRecipients([]);
      setComposeSubject("");
      setComposeBody("");
      setComposeAttachments([]);

      setSelectedFolder("sent");
      await fetchMail();
      if (res.alert_id) {
        await handleSelectMessage(res.alert_id);
      }
    } catch (err: unknown) {
      setSendError(err instanceof Error ? err.message : "Failed to send message.");
    } finally {
      setIsSendingMail(false);
    }
  };

  const toggleRecipient = (userId: string) => {
    setSelectedRecipients((prev) =>
      prev.includes(userId) ? prev.filter((u) => u !== userId) : [...prev, userId]
    );
  };

  const handleSelectMessage = async (msgId: number) => {
    setSelectedMessageId(msgId);
    setExecutionResult(null);
    setExecutionError(null);
    try {
      let detail: MailMessageDetail;
      try {
        detail = await mailApi.get(msgId);
      } catch {
        const secDetail = await securityApi.alertDetail(msgId);
        detail = secDetail as unknown as MailMessageDetail;
      }
      setSelectedDetail(detail);
      if (!detail.is_read) {
        try {
          await mailApi.markRead(msgId);
        } catch {
          await securityApi.markAlertRead(msgId);
        }
        setMessages((prev) =>
          prev.map((m) => (m.id === msgId ? { ...m, is_read: 1 } : m))
        );
        setUnreadCount((c) => Math.max(0, c - 1));
      }
    } catch (err) {
      console.error("Failed to load message detail:", err);
    }
  };

  const handleDispatchTest = async () => {
    setIsDispatching(true);
    try {
      try {
        await mailApi.dispatchTest();
      } catch {
        await securityApi.dispatchTestAlert();
      }
      await fetchMail();
    } catch (err) {
      console.error("Test alert failed:", err);
    } finally {
      setIsDispatching(false);
    }
  };

  const handleClearMailbox = async () => {
    if (!window.confirm("Purge all messages in internal mailbox (Admin only)?")) return;
    try {
      try {
        await mailApi.clear();
      } catch {
        await securityApi.clearMailbox();
      }
      setSelectedMessageId(null);
      setSelectedDetail(null);
      await fetchMail();
    } catch (err) {
      console.error("Clear mailbox failed:", err);
    }
  };

  const handleRequestPermit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedWorkspaceId) return;
    setIsSubmittingRequest(true);
    try {
      await authorizationsApi.create({
        workspace_id: selectedWorkspaceId,
        action: requestAction,
        resource: requestResource,
        valid_duration_minutes: Number(requestDuration),
        reason: requestReason,
      });
      setShowRequestModal(false);
      await fetchMail();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Permit request failed.");
    } finally {
      setIsSubmittingRequest(false);
    }
  };

  const handleExecutePermit = async () => {
    if (!selectedDetail || !selectedDetail.evidence_pack?.permit_code) return;
    const permitCode = selectedDetail.evidence_pack.permit_code;
    const action = selectedDetail.evidence_pack.tool_name?.split(" ")[0] || "operate_pump";
    const resource = selectedDetail.evidence_pack.tool_name?.match(/\[(.*?)\]/)?.[1] || "P-101A";

    setIsExecutingPermit(true);
    setExecutionError(null);
    setExecutionResult(null);
    setShowConfirmModal(false);

    try {
      const res = await authorizationsApi.execute({
        permit_code: permitCode,
        action: action,
        resource: resource,
      });
      setExecutionResult(res);
      // Reload detail to update state
      await handleSelectMessage(selectedDetail.id);
      await fetchMail();
    } catch (err: unknown) {
      setExecutionError(err instanceof Error ? err.message : "Execution denied.");
    } finally {
      setIsExecutingPermit(false);
    }
  };

  const filteredMessages = messages.filter((m) => {
    if (filterUnreadOnly && m.is_read) return false;
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      m.subject.toLowerCase().includes(q) ||
      m.sender.toLowerCase().includes(q) ||
      m.alert_type.toLowerCase().includes(q) ||
      (m.related_user && m.related_user.toLowerCase().includes(q))
    );
  });

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case "CRITICAL":
        return "bg-status-error/15 text-status-error border border-status-error/30";
      case "HIGH":
        return "bg-orange-500/15 text-orange-400 border border-orange-500/30";
      case "MEDIUM":
        return "bg-status-warning/15 text-status-warning border border-status-warning/30";
      case "LOW":
      default:
        return "bg-blue-500/15 text-blue-400 border border-blue-500/30";
    }
  };

  const isPermit =
    selectedDetail?.alert_type === "ACCESS_AUTHORIZATION" ||
    Boolean(selectedDetail?.evidence_pack?.permit_code);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] p-4 gap-3">
      <div className="flex items-center justify-between">
        <PageHeader
          title="Sovereign Industrial Mailbox"
          description={`Internal Messaging · Role: ${role ?? "operator"}`}
        />
        <div className="flex items-center gap-2">
          {smtpHealth && (
            <div
              className={`flex items-center gap-1.5 rounded border px-2.5 py-1 text-[11px] font-mono ${
                smtpHealth.status === "ACTIVE"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                  : "border-status-error/40 bg-status-error/10 text-status-error"
              }`}
              title={smtpHealth.banner || smtpHealth.error}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  smtpHealth.status === "ACTIVE" ? "bg-emerald-400 animate-pulse" : "bg-status-error"
                }`}
              />
              <span>SMTP {smtpHealth.host}:{smtpHealth.port}</span>
            </div>
          )}
          <Button
            size="sm"
            variant="primary"
            onClick={openComposeModal}
            className="bg-brand text-black font-semibold hover:bg-brand/90"
          >
            <IconMail className="h-3.5 w-3.5 mr-1" />
            Compose
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setShowRequestModal(true)}
          >
            + Request Permit
          </Button>
          {(role === "supervisor" || role === "administrator") && (
            <Button
              size="sm"
              variant="secondary"
              disabled={isDispatching}
              onClick={handleDispatchTest}
              className="hidden sm:inline-flex"
            >
              {isDispatching ? "Dispatching..." : "Test Alert"}
            </Button>
          )}
          {role === "administrator" && messages.length > 0 && (
            <Button
              size="sm"
              variant="secondary"
              className="border-status-error/40 text-status-error hover:bg-status-error/10 hidden sm:inline-flex"
              onClick={handleClearMailbox}
            >
              <IconTrash className="h-3.5 w-3.5 mr-1" />
              Clear
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={() => void fetchMail()}>
            <IconRefresh className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Mobile folder pills (visible only on mobile) */}
      <div className="flex md:hidden items-center gap-1 overflow-x-auto pb-1 text-xs shrink-0">
        {[
          { key: "all", label: "Inbound" },
          { key: "sent", label: "Sent" },
          { key: "permits", label: "Permits" },
          { key: "security", label: "Security" },
          { key: "governance", label: "Governance" },
        ].map((f) => (
          <button
            key={f.key}
            onClick={() => {
              setSelectedFolder(f.key as FolderType);
              setSelectedMessageId(null);
            }}
            className={`whitespace-nowrap px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
              selectedFolder === f.key
                ? "bg-brand text-black border-brand font-bold"
                : "bg-surface-2 text-ink-2 border-surface-border"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* 3-PANE EMAIL CLIENT LAYOUT */}
      <div className="flex flex-1 min-h-0 rounded-xl border border-surface-border bg-surface-1 overflow-hidden shadow-2xl">
        {/* PANE 1: FOLDERS & CATEGORIES */}
        <div className="hidden md:flex w-52 lg:w-56 border-r border-surface-border bg-surface-2/40 flex-col justify-between p-3 shrink-0">
          <div className="space-y-4">
            <div>
              <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink-3 px-2">
                Mailboxes
              </span>
              <div className="mt-2 space-y-1">
                {[
                  { key: "all", label: "All Inbound", count: totalCount, icon: IconInbox },
                  { key: "sent", label: "Sent Messages", icon: IconMail },
                  { key: "permits", label: "Work Permits", icon: IconShieldCheck },
                  { key: "security", label: "Security Events", icon: IconAlertTriangle },
                  { key: "governance", label: "Four-Eyes / Gov", icon: IconCheck },
                ].map((f) => {
                  const IconComponent = f.icon;
                  const isActive = selectedFolder === f.key;
                  return (
                    <button
                      key={f.key}
                      onClick={() => {
                        setSelectedFolder(f.key as FolderType);
                        setSelectedMessageId(null);
                      }}
                      className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                        isActive
                          ? "bg-brand/15 text-brand font-semibold"
                          : "text-ink-2 hover:bg-surface-3 hover:text-ink-1"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <IconComponent className="h-4 w-4" />
                        <span>{f.label}</span>
                      </div>
                      {f.key === "all" && unreadCount > 0 && (
                        <span className="rounded-full bg-brand px-1.5 py-0.2 font-mono text-[10px] font-bold text-black">
                          {unreadCount}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="border-t border-surface-border pt-3">
              <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink-3 px-2">
                Quick Filter
              </span>
              <button
                onClick={() => setFilterUnreadOnly((v) => !v)}
                className={`mt-2 flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  filterUnreadOnly
                    ? "bg-blue-500/15 text-blue-400 font-semibold"
                    : "text-ink-2 hover:bg-surface-3 hover:text-ink-1"
                }`}
              >
                <span>Unread Only</span>
                {unreadCount > 0 && (
                  <span className="h-2 w-2 rounded-full bg-blue-400" />
                )}
              </button>
            </div>
          </div>

          {/* Transport status. Only assert what the health endpoint verified. */}
          <div className="rounded-lg border border-surface-border bg-surface-2 p-2.5 text-[11px] font-mono text-ink-3 space-y-1">
            <div className="flex items-center justify-between">
              <span>Transport scope:</span>
              <span className={smtpHealth?.loopback_only ? "text-emerald-400 font-bold" : "text-status-warning font-bold"}>
                {smtpHealth ? (smtpHealth.loopback_only ? "LOCAL ONLY" : "NOT VERIFIED") : "UNAVAILABLE"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>Transport:</span>
              <span className="text-ink-2">
                {smtpHealth ? `${smtpHealth.host}:${smtpHealth.port}` : "Unavailable"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>Internet status:</span>
              <span className="text-status-warning font-bold">NOT VERIFIED</span>
            </div>
          </div>
        </div>

        {/* PANE 2: SEARCHABLE MESSAGE LIST */}
        <div className={`${selectedMessageId !== null ? "hidden md:flex" : "flex"} w-full md:w-80 lg:w-96 border-r border-surface-border flex-col bg-surface-1 shrink-0`}>
          <div className="p-2.5 border-b border-surface-border">
            <input
              type="text"
              placeholder="Search subjects, users, permits..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-xs text-ink-1 placeholder:text-ink-3 focus:border-brand focus:outline-none"
            />
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-surface-border">
            {isLoading ? (
              <div className="flex h-32 items-center justify-center text-xs text-ink-3 gap-2">
                <IconLoader className="h-4 w-4 animate-spin text-brand" />
                Loading mailbox...
              </div>
            ) : fetchError ? (
              <div className="p-8 text-center text-xs">
                <p className="text-status-warning mb-2">{fetchError}</p>
                <Button size="sm" variant="secondary" onClick={() => void fetchMail()}>
                  Retry Connection
                </Button>
              </div>
            ) : filteredMessages.length === 0 ? (
              <div className="p-8 text-center text-xs text-ink-3">
                No messages found in this folder.
              </div>
            ) : (
              filteredMessages.map((msg) => {
                const isSelected = msg.id === selectedMessageId;
                return (
                  <div
                    key={msg.id}
                    onClick={() => void handleSelectMessage(msg.id)}
                    className={`p-3 transition-colors cursor-pointer text-left ${
                      isSelected
                        ? "bg-brand/10 border-l-2 border-brand"
                        : msg.is_read
                        ? "hover:bg-surface-2"
                        : "bg-blue-500/5 hover:bg-surface-2 font-medium"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-1.5 min-w-0">
                        {!msg.is_read ? (
                          <span className="h-2 w-2 rounded-full bg-blue-400 shrink-0" title="Unread" />
                        ) : (
                          <span className="h-2 w-2 rounded-full bg-transparent shrink-0" />
                        )}
                        <span className="truncate text-xs font-semibold text-ink-1">
                          {msg.sender.split("@")[0]}
                        </span>
                      </div>
                      <span className="font-mono text-[10px] text-ink-3 shrink-0">
                        {formatRelativeTime(msg.created_at)}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 mb-1">
                      <span className={`rounded px-1.5 py-0.2 font-mono text-[9px] font-bold uppercase ${getSeverityBadge(msg.severity)}`}>
                        {msg.severity}
                      </span>
                      <span className="rounded bg-surface-3 px-1.5 py-0.2 font-mono text-[9px] text-ink-3 truncate">
                        {msg.alert_type}
                      </span>
                    </div>

                    <p className="text-xs text-ink-2 truncate font-medium">{msg.subject}</p>
                    {msg.related_user && (
                      <p className="text-[10px] font-mono text-ink-3 mt-1">
                        Operator: <span className="text-brand font-medium">{msg.related_user}</span>
                      </p>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* PANE 3: DETAILED PREVIEW & EXECUTION PANE */}
        <div className={`${selectedMessageId === null ? "hidden md:flex" : "flex"} flex-1 flex-col min-w-0 bg-surface-2/20 overflow-y-auto`}>
          {!selectedDetail ? (
            <div className="flex h-full items-center justify-center flex-col text-xs text-ink-3 gap-2 p-6">
              <IconInbox className="h-8 w-8 text-ink-3/40" />
              <span>Select an email or work permit from the list to preview details.</span>
            </div>
          ) : (
            <div className="p-4 md:p-6 space-y-5 max-w-4xl">
              {/* Mobile Back Button */}
              <div className="md:hidden pb-2 border-b border-surface-border flex items-center justify-between">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setSelectedMessageId(null);
                    setSelectedDetail(null);
                  }}
                  className="text-xs"
                >
                  ← Back to Messages
                </Button>
                <span className="font-mono text-[10px] text-ink-3">
                  ID: #{selectedDetail.id}
                </span>
              </div>

              {/* Header */}
              <div className="border-b border-surface-border pb-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`rounded px-2 py-0.5 font-mono text-[11px] font-bold uppercase ${getSeverityBadge(selectedDetail.severity)}`}>
                      {selectedDetail.severity}
                    </span>
                    <span className="rounded bg-surface-3 px-2 py-0.5 font-mono text-[11px] text-ink-3">
                      {selectedDetail.alert_type}
                    </span>
                    <span className="font-mono text-[10px] text-ink-3">
                      Mode: {selectedDetail.composition_mode}
                    </span>
                  </div>
                  <div className="font-mono text-xs text-ink-3">
                    {formatFullDateTime(selectedDetail.created_at)}
                  </div>
                </div>

                <h2 className="text-lg font-bold text-ink-1">{selectedDetail.subject}</h2>

                <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-ink-3">
                  <div>From: <span className="text-ink-1 font-semibold">{selectedDetail.sender}</span></div>
                  <div>To: <span className="text-ink-1">{selectedDetail.recipients.join(", ")}</span></div>
                  {selectedDetail.read_at && (
                    <div>Read at: <span className="text-ink-2">{formatIstTime(selectedDetail.read_at)} IST</span></div>
                  )}
                </div>
              </div>

              {/* ACTIVE PERMIT EXECUTION CALLOUT */}
              {isPermit && (
                <div className="rounded-xl border border-brand/40 bg-brand/5 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <IconShieldCheck className="h-5 w-5 text-brand" />
                      <span className="font-mono text-xs font-bold uppercase tracking-wider text-brand">
                        Operational Work Permit Notice
                      </span>
                    </div>
                    <span className="rounded bg-brand/20 px-2 py-0.5 font-mono text-[11px] font-bold text-brand">
                      {selectedDetail.evidence_pack?.permit_code || "ACTIVE"}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs font-mono">
                    <div>
                      <span className="text-ink-3 block">Authorized User:</span>
                      <span className="text-brand font-bold">{selectedDetail.related_user || role || "operator"}</span>
                    </div>
                    <div>
                      <span className="text-ink-3 block">Target Asset:</span>
                      <span className="text-ink-1 font-bold">
                        {selectedDetail.evidence_pack?.tool_name?.match(/\[(.*?)\]/)?.[1] || "P-101A"}
                      </span>
                    </div>
                    <div>
                      <span className="text-ink-3 block">Action Scope:</span>
                      <span className="text-ink-1 font-bold">
                        {selectedDetail.evidence_pack?.tool_name?.split(" ")[0] || "operate_pump"}
                      </span>
                    </div>
                    <div>
                      <span className="text-ink-3 block">Permitted Uses:</span>
                      <span className="text-ink-1 font-bold">
                        {selectedDetail.alert_type === "AUTHORIZATION_CONSUMED" ? "0 / 1 (CONSUMED)" : "1 / 1 (READY)"}
                      </span>
                    </div>
                  </div>

                  {/* EXECUTION ACTION BUTTON */}
                  <div className="pt-2 border-t border-brand/20 flex flex-wrap items-center justify-between gap-2">
                    <div className="text-[11px] text-ink-3 font-mono">
                      [SIMULATED INDUSTRIAL ACTION - SIH FINALS PROTOTYPE]
                    </div>
                    {selectedDetail.alert_type === "AUTHORIZATION_CONSUMED" ? (
                      <span className="rounded border border-surface-border bg-surface-3 px-3 py-1 text-xs font-mono font-bold text-ink-3">
                        PERMIT CONSUMED (Uses Expended)
                      </span>
                    ) : (
                      <Button
                        size="sm"
                        variant="primary"
                        disabled={isExecutingPermit}
                        onClick={() => setShowConfirmModal(true)}
                        className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
                      >
                        <IconPlay className="h-3.5 w-3.5 mr-1" />
                        Execute Authorized Action (Simulated)
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {/* EXECUTION RESULT DISPLAY */}
              {executionResult && (
                <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-4 space-y-2">
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs font-mono">
                    <IconCheck className="h-4 w-4" />
                    SIMULATED ACTION EXECUTED · ONE-TIME PERMIT CONSUMED ({executionResult.latency_ms}ms)
                  </div>
                  <div className="rounded bg-surface-1 p-3 font-mono text-xs text-emerald-300 leading-relaxed border border-surface-border">
                    {executionResult.simulated_result}
                  </div>
                  <p className="font-mono text-[10px] text-ink-3">
                    Status: <strong className="text-status-error uppercase">{executionResult.status}</strong> · Remaining Permitted Uses: 0
                  </p>
                </div>
              )}

              {/* EXECUTION ERROR DISPLAY */}
              {executionError && (
                <div className="rounded-xl border border-status-error/40 bg-status-error/10 p-4 space-y-1">
                  <div className="flex items-center gap-2 text-status-error font-bold text-xs font-mono">
                    <IconAlertTriangle className="h-4 w-4" />
                    EXECUTION INTERCEPTED & REJECTED
                  </div>
                  <p className="font-mono text-xs text-status-error">{executionError}</p>
                </div>
              )}

              {/* View Mode Toggle: Sanitized HTML vs RFC Plain text */}
              <div className="flex items-center justify-between border-b border-surface-border pb-1">
                <span className="font-mono text-xs font-bold uppercase tracking-wider text-ink-3">
                  Message Content
                </span>
                <div className="flex items-center gap-1 rounded bg-surface-3 p-0.5">
                  <button
                    onClick={() => setBodyViewMode("html")}
                    className={`rounded px-2 py-0.5 text-xs font-mono transition-colors ${
                      bodyViewMode === "html" ? "bg-surface-1 font-bold text-ink-1 shadow" : "text-ink-3 hover:text-ink-1"
                    }`}
                  >
                    HTML
                  </button>
                  <button
                    onClick={() => setBodyViewMode("text")}
                    className={`rounded px-2 py-0.5 text-xs font-mono transition-colors ${
                      bodyViewMode === "text" ? "bg-surface-1 font-bold text-ink-1 shadow" : "text-ink-3 hover:text-ink-1"
                    }`}
                  >
                    Plain Text
                  </button>
                </div>
              </div>

              {/* Body Content Render */}
              {bodyViewMode === "html" && selectedDetail.body_html ? (
                <div className="rounded-lg border border-surface-border bg-white overflow-hidden text-black">
                  <iframe
                    title="Email Preview"
                    srcDoc={selectedDetail.body_html}
                    className="w-full h-80 border-0"
                    sandbox="allow-same-origin"
                  />
                </div>
              ) : (
                <div className="rounded-lg border border-surface-border bg-surface-1 p-4 font-mono text-xs leading-relaxed text-ink-1 whitespace-pre-wrap">
                  {selectedDetail.body_text}
                </div>
              )}

              {/* ATTACHMENTS SECTION */}
              {selectedDetail.attachments && selectedDetail.attachments.length > 0 && (
                <div className="rounded-lg border border-surface-border bg-surface-2/60 p-3 space-y-2">
                  <div className="flex items-center gap-2 font-mono text-[11px] font-bold text-ink-2 uppercase tracking-wider">
                    <IconDownload className="h-3.5 w-3.5 text-brand" />
                    <span>Attached Files ({selectedDetail.attachments.length})</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {selectedDetail.attachments.map((att) => (
                      <button
                        type="button"
                        key={att.id}
                        onClick={async () => {
                          try {
                            setFetchError(null);
                            await mailApi.downloadAttachment(selectedDetail.id, att.id, att.filename);
                          } catch (err) {
                            setFetchError(err instanceof Error ? err.message : "Attachment download failed");
                          }
                        }}
                        className="flex items-center justify-between rounded-lg border border-surface-border bg-surface-1 p-2.5 hover:border-brand/40 transition-colors group"
                      >
                        <div className="min-w-0 flex items-center gap-2">
                          <span className="font-mono text-base">📎</span>
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-ink-1 truncate group-hover:text-brand transition-colors">
                              {att.filename}
                            </p>
                            <p className="font-mono text-[10px] text-ink-3">
                              {(att.file_size / 1024).toFixed(1)} KB · {att.content_type.split("/")[1] || "file"}
                            </p>
                          </div>
                        </div>
                        <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center">
                          <IconDownload className="h-3.5 w-3.5 text-ink-2 group-hover:text-brand" />
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Verified Authoritative Citations */}
              <div className="space-y-2">
                <h4 className="font-mono text-[11px] uppercase tracking-wider text-ink-3 font-bold">
                  Authoritative Grounding Citations ({selectedDetail.citations?.length || 0})
                </h4>
                {(!selectedDetail.citations || selectedDetail.citations.length === 0) ? (
                  <p className="text-xs text-ink-3">No external citations attached.</p>
                ) : (
                  <div className="space-y-2">
                    {selectedDetail.citations.map((c) => (
                      <div
                        key={c.id}
                        className="flex items-center justify-between rounded-lg border border-surface-border bg-surface-1 px-3 py-2 text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-brand">[{c.citation_index}]</span>
                            <span className="rounded bg-surface-3 px-1.5 py-0.2 font-mono text-[10px] text-ink-2">
                              {c.citation_class}
                            </span>
                            <span className="font-semibold text-ink-1">{c.display_label}</span>
                          </div>
                          <p className="font-mono text-[10px] text-ink-3">
                            Source ID: {c.source_id} {c.page_number ? `· Page ${c.page_number}` : ""}
                          </p>
                        </div>
                        <span className="rounded bg-emerald-500/15 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-400 border border-emerald-500/30">
                          VERIFIED
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Registered Work Permit Artifact */}
              {selectedDetail.artifact && (
                <div className="rounded-lg border border-surface-border bg-surface-1 p-3 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-ink-3 font-bold block">
                      Official Document Deliverable
                    </span>
                    <p className="text-xs font-semibold text-ink-1">{selectedDetail.artifact.filename}</p>
                    <p className="font-mono text-[10px] text-ink-3 truncate">
                      SHA256: {selectedDetail.artifact.sha256_hash.slice(0, 24)}... ({Math.round(selectedDetail.artifact.file_size / 1024)} KB)
                    </p>
                  </div>
                  <a
                    href={`/api/v1/workspaces/${selectedWorkspaceId || 1}/artifacts/${selectedDetail.artifact.id}/download`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Button size="sm" variant="secondary">
                      <IconDownload className="h-3.5 w-3.5 mr-1" />
                      Download Permit
                    </Button>
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* CONFIRMATION MODAL FOR ATOMIC PERMIT EXECUTION */}
      {showConfirmModal && selectedDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-surface-border bg-surface-1 p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2.5 text-status-warning">
              <IconAlertTriangle className="h-5 w-5" />
              <h3 className="font-bold text-base text-ink-1">Confirm Operational Execution</h3>
            </div>

            <div className="rounded-lg border border-surface-border bg-surface-2 p-3 text-xs font-mono space-y-1.5">
              <div><span className="text-ink-3">Permit Code:</span> <span className="text-brand font-bold">{selectedDetail.evidence_pack?.permit_code}</span></div>
              <div><span className="text-ink-3">Equipment:</span> <span className="text-ink-1 font-semibold">{selectedDetail.evidence_pack?.tool_name?.match(/\[(.*?)\]/)?.[1] || "P-101A"}</span></div>
              <div><span className="text-ink-3">Action:</span> <span className="text-ink-1 font-semibold">{selectedDetail.evidence_pack?.tool_name?.split(" ")[0] || "operate_pump"}</span></div>
              <div><span className="text-ink-3">Remaining Uses:</span> <span className="text-ink-1 font-semibold">1 (Single-Use Permit)</span></div>
            </div>

            <div className="rounded bg-status-warning/10 border border-status-warning/30 p-2.5 text-[11px] font-mono text-status-warning leading-relaxed">
              [SIMULATED INDUSTRIAL ACTION - SIH FINALS PROTOTYPE]
              <br />
              This action will atomically consume this one-time permit. A second execution attempt will fail closed.
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-surface-border">
              <Button
                variant="secondary"
                onClick={() => setShowConfirmModal(false)}
                disabled={isExecutingPermit}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleExecutePermit}
                disabled={isExecutingPermit}
                className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
              >
                {isExecutingPermit ? "Executing..." : "Execute & Consume Permit"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* REQUEST WORK PERMIT MODAL */}
      {showRequestModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <form onSubmit={handleRequestPermit} className="w-full max-w-lg rounded-xl border border-surface-border bg-surface-1 p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <h3 className="font-bold text-base text-ink-1">Request Operational Work Permit</h3>
              <button
                type="button"
                onClick={() => setShowRequestModal(false)}
                className="text-ink-3 hover:text-ink-1 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-ink-3 font-mono mb-1 font-medium">Target Industrial Equipment</label>
                <input
                  type="text"
                  value={requestResource}
                  onChange={(e) => setRequestResource(e.target.value)}
                  className="w-full rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-xs text-ink-1 font-mono focus:border-brand focus:outline-none"
                  placeholder="e.g. P-101A (Centrifugal Pump)"
                  required
                />
              </div>

              <div>
                <label className="block text-ink-3 font-mono mb-1 font-medium">Requested Action / Tool</label>
                <select
                  value={requestAction}
                  onChange={(e) => setRequestAction(e.target.value)}
                  className="w-full rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-xs text-ink-1 font-mono focus:border-brand focus:outline-none"
                >
                  <option value="operate_pump">operate_pump (Energize Centrifugal Pump Starter)</option>
                  <option value="restart_component">restart_component (Motor Breaker Re-engage)</option>
                  <option value="check_pressure">check_pressure (Surge Line Diagnostic)</option>
                  <option value="emergency_pressure_relief">emergency_pressure_relief (Pilot Valve SV-402)</option>
                </select>
              </div>

              <div>
                <label className="block text-ink-3 font-mono mb-1 font-medium">Validity Duration (Minutes)</label>
                <input
                  type="number"
                  min="5"
                  max="1440"
                  value={requestDuration}
                  onChange={(e) => setRequestDuration(Number(e.target.value))}
                  className="w-full rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-xs text-ink-1 font-mono focus:border-brand focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-ink-3 font-mono mb-1 font-medium">Operational Justification / Reason</label>
                <textarea
                  rows={2}
                  value={requestReason}
                  onChange={(e) => setRequestReason(e.target.value)}
                  className="w-full rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-xs text-ink-1 font-mono focus:border-brand focus:outline-none"
                  required
                />
              </div>

              <div className="rounded bg-surface-2 p-2.5 text-[11px] font-mono text-ink-3">
                Governance: This request will be submitted in <strong>PENDING_APPROVAL (0/2)</strong>. It requires two independent authenticated supervisor approvals (Zara + Rakshita) before becoming active.
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-surface-border">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowRequestModal(false)}
                disabled={isSubmittingRequest}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                disabled={isSubmittingRequest}
              >
                {isSubmittingRequest ? "Submitting..." : "Submit Permit Request"}
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* GENUINE USER-TO-USER MAIL COMPOSE MODAL */}
      {showComposeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-3 md:p-4 backdrop-blur-sm">
          <form
            onSubmit={handleSendMail}
            className="w-full max-w-2xl rounded-xl border border-surface-border bg-surface-1 p-5 space-y-4 shadow-2xl max-h-[92vh] flex flex-col"
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-surface-border pb-3 shrink-0">
              <div className="flex items-center gap-2">
                <IconMail className="h-4 w-4 text-brand" />
                <h3 className="font-bold text-base text-ink-1">Compose Internal Message</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowComposeModal(false)}
                className="text-ink-3 hover:text-ink-1 text-sm font-bold p-1"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs overflow-y-auto pr-1 flex-1">
              {/* Recipients Selection */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-ink-3 font-mono font-medium">
                    Recipients (Select team members)
                  </label>
                  <input
                    type="text"
                    placeholder="Filter names..."
                    value={recipientFilter}
                    onChange={(e) => setRecipientFilter(e.target.value)}
                    className="rounded border border-surface-border bg-surface-2 px-2 py-0.5 text-[11px] text-ink-1 focus:border-brand focus:outline-none"
                  />
                </div>
                <div className="flex flex-wrap gap-1.5 p-2 rounded border border-surface-border bg-surface-2 min-h-[38px] max-h-28 overflow-y-auto">
                  {availableRecipients.length === 0 ? (
                    <span className="text-ink-3 text-xs">Loading team directory...</span>
                  ) : (
                    availableRecipients
                      .filter((r) =>
                        !recipientFilter.trim() ||
                        r.display_name.toLowerCase().includes(recipientFilter.toLowerCase()) ||
                        r.role.toLowerCase().includes(recipientFilter.toLowerCase()) ||
                        r.user_id.toLowerCase().includes(recipientFilter.toLowerCase())
                      )
                      .map((rec) => {
                        const isSelected = selectedRecipients.includes(rec.user_id);
                        return (
                          <button
                            key={rec.user_id}
                            type="button"
                            onClick={() => toggleRecipient(rec.user_id)}
                            className={`rounded-full px-2.5 py-1 text-xs font-mono transition-colors flex items-center gap-1.5 border ${
                              isSelected
                                ? "bg-brand text-black border-brand font-bold shadow-sm"
                                : "bg-surface-1 text-ink-2 border-surface-border hover:border-ink-3"
                            }`}
                          >
                            <span>{rec.display_name}</span>
                            <span className={`text-[10px] opacity-75 ${isSelected ? "text-black" : "text-ink-3"}`}>
                              ({rec.role})
                            </span>
                          </button>
                        );
                      })
                  )}
                </div>
                {selectedRecipients.length > 0 && (
                  <p className="font-mono text-[10px] text-ink-3 mt-1">
                    Selected ({selectedRecipients.length}): {selectedRecipients.join(", ")}
                  </p>
                )}
              </div>

              {/* Subject + AI Assist Trigger */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-ink-3 font-mono font-medium">Subject</label>
                  <button
                    type="button"
                    onClick={() => setShowAiAssist((v) => !v)}
                    className="text-brand hover:underline font-mono text-[11px] flex items-center gap-1 font-semibold"
                  >
                    <span>✨ Improve with Local AI</span>
                  </button>
                </div>
                <input
                  type="text"
                  value={composeSubject}
                  onChange={(e) => setComposeSubject(e.target.value)}
                  placeholder="e.g. Unit 4 Scheduled Inspection & Maintenance Handoff"
                  className="w-full rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-xs text-ink-1 font-medium focus:border-brand focus:outline-none"
                  required
                />
              </div>

              {/* Local AI Assistant Box */}
              {showAiAssist && (
                <div className="rounded-lg border border-brand/40 bg-brand/5 p-3 space-y-2">
                  <div className="flex items-center justify-between text-xs font-mono font-bold text-brand">
                    <span>Local Operational Draft Assistant</span>
                    <button
                      type="button"
                      onClick={() => setShowAiAssist(false)}
                      className="text-ink-3 hover:text-ink-1"
                    >
                      ✕
                    </button>
                  </div>
                  <p className="text-[11px] text-ink-3">
                    Describe your operational goal. The configured local model will generate a structured subject and email body.
                  </p>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={aiIntent}
                      onChange={(e) => setAiIntent(e.target.value)}
                      placeholder="e.g. Request Zara to approve urgent seal repair on pump P-101A"
                      className="flex-1 rounded border border-surface-border bg-surface-1 px-3 py-1.5 text-xs text-ink-1 focus:border-brand focus:outline-none"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          void handleGenerateAiDraft();
                        }
                      }}
                    />
                    <Button
                      type="button"
                      size="sm"
                      variant="primary"
                      disabled={isGeneratingAiDraft || !aiIntent.trim()}
                      onClick={handleGenerateAiDraft}
                    >
                      {isGeneratingAiDraft ? "Drafting..." : "Generate"}
                    </Button>
                  </div>
                </div>
              )}
              {aiDraftStatus && (
                <p
                  className={`font-mono text-[10px] ${
                    aiDraftStatus.includes("fallback") ? "text-status-warning" : "text-emerald-400"
                  }`}
                >
                  {aiDraftStatus}
                </p>
              )}

              {/* Message Body */}
              <div>
                <label className="block text-ink-3 font-mono mb-1 font-medium">Message Body</label>
                <textarea
                  rows={6}
                  value={composeBody}
                  onChange={(e) => setComposeBody(e.target.value)}
                  placeholder="Enter clear, professional operational communications..."
                  className="w-full rounded border border-surface-border bg-surface-2 px-3 py-2 text-xs text-ink-1 font-sans leading-relaxed focus:border-brand focus:outline-none resize-none"
                  required
                />
              </div>

              {/* Attachments Upload & Chips */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-ink-3 font-mono font-medium">
                    Attachments (Max 10MB: .pdf, .docx, .xlsx, .csv, .txt, .png, .jpg)
                  </label>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploadingAttachment}
                    className="text-brand hover:underline font-mono text-[11px] font-semibold"
                  >
                    {isUploadingAttachment ? "Uploading..." : "+ Add File"}
                  </button>
                </div>

                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleAttachmentUpload}
                  className="hidden"
                  accept=".pdf,.docx,.xlsx,.csv,.txt,.png,.jpg,.jpeg"
                />

                {composeAttachments.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {composeAttachments.map((att) => (
                      <div
                        key={att.id}
                        className="flex items-center gap-2 rounded-lg border border-surface-border bg-surface-2 px-2.5 py-1 text-xs font-mono"
                      >
                        <span className="text-ink-1 font-medium truncate max-w-[180px]">
                          {att.filename}
                        </span>
                        <span className="text-ink-3 text-[10px]">
                          ({(att.file_size / 1024).toFixed(1)} KB)
                        </span>
                        <button
                          type="button"
                          onClick={() => removeAttachment(att.id)}
                          className="text-status-error hover:text-status-error/80 font-bold ml-1"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {attachmentError && (
                  <p className="font-mono text-[10px] text-status-error mt-1">{attachmentError}</p>
                )}
              </div>

              {sendError && (
                <div className="rounded border border-status-error/40 bg-status-error/10 p-2 text-xs font-mono text-status-error">
                  {sendError}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between pt-3 border-t border-surface-border shrink-0">
              <span className="font-mono text-[10px] text-ink-3">
                Sender: <strong>{currentUserId || "not-verified"}@secure.internal</strong>
              </span>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setShowComposeModal(false)}
                  disabled={isSendingMail}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={isSendingMail || selectedRecipients.length === 0}
                  className="bg-brand text-black font-semibold"
                >
                  {isSendingMail ? "Sending..." : "Send Message"}
                </Button>
              </div>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
