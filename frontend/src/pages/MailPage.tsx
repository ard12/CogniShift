import { useCallback, useEffect, useState } from "react";
import { mailApi, type MailMessageMetadata, type MailMessageDetail, type SmtpHealthStatus } from "@/api/mail";
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

type FolderType = "all" | "permits" | "security" | "governance";

export function MailPage() {
  const { role } = useAuth();
  const { selectedWorkspaceId } = useWorkspaces();
  const [messages, setMessages] = useState<MailMessageMetadata[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [selectedFolder, setSelectedFolder] = useState<FolderType>("all");
  const [filterUnreadOnly, setFilterUnreadOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [selectedMessageId, setSelectedMessageId] = useState<number | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<MailMessageDetail | null>(null);
  const [bodyViewMode, setBodyViewMode] = useState<"html" | "text">("html");

  const [smtpHealth, setSmtpHealth] = useState<SmtpHealthStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
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

  const fetchMail = useCallback(async () => {
    try {
      const folderParam = selectedFolder === "all" ? undefined : selectedFolder;
      const res = await mailApi.list(folderParam, 100, 0);
      setMessages(res.messages);
      setUnreadCount(res.unread_count);
      setTotalCount(res.total_count);
      try {
        setSmtpHealth(await mailApi.smtpHealth());
      } catch {
        // Ignore SMTP health poll fail
      }
    } catch (err) {
      console.error("Mailbox fetch failed:", err);
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

  const handleSelectMessage = async (msgId: number) => {
    setSelectedMessageId(msgId);
    setExecutionResult(null);
    setExecutionError(null);
    try {
      const detail = await mailApi.get(msgId);
      setSelectedDetail(detail);
      if (!detail.is_read) {
        await mailApi.markRead(msgId);
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
      await mailApi.dispatchTest();
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
      await mailApi.clear();
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
    } catch (err: any) {
      const msg = err?.message || err?.detail || "Execution denied.";
      setExecutionError(typeof msg === "string" ? msg : JSON.stringify(msg));
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
          description={`Air-Gapped Loopback Internal Messaging · Role: ${role ?? "operator"}`}
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
              <span>SMTP {smtpHealth.host}:{smtpHealth.port} ({smtpHealth.status})</span>
            </div>
          )}
          <Button
            size="sm"
            variant="primary"
            onClick={() => setShowRequestModal(true)}
          >
            + Request Work Permit
          </Button>
          {(role === "supervisor" || role === "administrator") && (
            <Button
              size="sm"
              variant="secondary"
              disabled={isDispatching}
              onClick={handleDispatchTest}
            >
              {isDispatching ? "Dispatching..." : "Dispatch Test Alert"}
            </Button>
          )}
          {role === "administrator" && messages.length > 0 && (
            <Button
              size="sm"
              variant="secondary"
              className="border-status-error/40 text-status-error hover:bg-status-error/10"
              onClick={handleClearMailbox}
            >
              <IconTrash className="h-3.5 w-3.5 mr-1" />
              Clear Mailbox
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={() => void fetchMail()}>
            <IconRefresh className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* 3-PANE EMAIL CLIENT LAYOUT */}
      <div className="flex flex-1 min-h-0 rounded-xl border border-surface-border bg-surface-1 overflow-hidden shadow-2xl">
        {/* PANE 1: FOLDERS & CATEGORIES */}
        <div className="w-56 border-r border-surface-border bg-surface-2/40 flex flex-col justify-between p-3 shrink-0">
          <div className="space-y-4">
            <div>
              <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink-3 px-2">
                Mailboxes
              </span>
              <div className="mt-2 space-y-1">
                {[
                  { key: "all", label: "All Inbound", count: totalCount, icon: IconInbox },
                  { key: "permits", label: "Work Permits", icon: IconShieldCheck },
                  { key: "security", label: "Security Events", icon: IconAlertTriangle },
                  { key: "governance", label: "Four-Eyes / Governance", icon: IconMail },
                ].map((f) => {
                  const IconComponent = f.icon;
                  const isActive = selectedFolder === f.key;
                  return (
                    <button
                      key={f.key}
                      onClick={() => setSelectedFolder(f.key as FolderType)}
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

          {/* Air gap telemetry status */}
          <div className="rounded-lg border border-surface-border bg-surface-2 p-2.5 text-[11px] font-mono text-ink-3 space-y-1">
            <div className="flex items-center justify-between">
              <span>Sovereignty:</span>
              <span className="text-emerald-400 font-bold">100% OFFLINE</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Transport:</span>
              <span className="text-ink-2">Loopback SMTP</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Egress:</span>
              <span className="text-emerald-400 font-bold">ZERO CLOUD</span>
            </div>
          </div>
        </div>

        {/* PANE 2: SEARCHABLE MESSAGE LIST */}
        <div className="w-80 md:w-96 border-r border-surface-border flex flex-col bg-surface-1 shrink-0">
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
        <div className="flex-1 flex flex-col min-w-0 bg-surface-2/20 overflow-y-auto">
          {!selectedDetail ? (
            <div className="flex h-full items-center justify-center flex-col text-xs text-ink-3 gap-2">
              <IconInbox className="h-8 w-8 text-ink-3/40" />
              <span>Select an email or work permit from the list to preview details.</span>
            </div>
          ) : (
            <div className="p-6 space-y-5 max-w-4xl">
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
                <div className="rounded-lg border border-surface-border bg-black/40 overflow-hidden">
                  <iframe
                    title="Email Preview"
                    srcDoc={selectedDetail.body_html}
                    className="w-full h-96 border-0"
                    sandbox="allow-same-origin"
                  />
                </div>
              ) : (
                <div className="rounded-lg border border-surface-border bg-surface-1 p-4 font-mono text-xs leading-relaxed text-ink-1 whitespace-pre-wrap">
                  {selectedDetail.body_text}
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
    </div>
  );
}
