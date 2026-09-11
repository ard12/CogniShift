import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { IconDownload, IconInbox } from "@/components/ui/Icon";
import { formatFullDateTime, formatIstTime } from "@/lib/format";
import { mailApi } from "@/api/mail";
import { getSeverityBadge } from "./mailUtils";
import { PermitMessageDetail } from "./PermitMessageDetail";
import { SecurityMessageDetail } from "./SecurityMessageDetail";
import { GovernanceMessageDetail } from "./GovernanceMessageDetail";
import { PermitConfirmModal } from "./PermitConfirmModal";
import { authorizationsApi } from "@/api/authorizations";
import type { MailMessageDetail as DetailType, ExecutionResult } from "./types";

interface MailMessageDetailProps {
  detail: DetailType | null;
  role: string | null;
  workspaceId: number | null;
  bodyViewMode: "html" | "text";
  onToggleBodyViewMode: (mode: "html" | "text") => void;
  onBackMobile: () => void;
  onDetailUpdated: () => void;
}

export function MailMessageDetail({
  detail,
  role,
  workspaceId,
  bodyViewMode,
  onToggleBodyViewMode,
  onBackMobile,
  onDetailUpdated,
}: MailMessageDetailProps) {
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [isExecutingPermit, setIsExecutingPermit] = useState(false);
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  if (!detail) {
    return (
      <div className="hidden md:flex flex-1 flex-col items-center justify-center text-xs text-ink-3 gap-2 p-6 bg-surface-2/20">
        <IconInbox className="h-8 w-8 text-ink-3/40" />
        <span>Select an email or work permit from the list to preview details.</span>
      </div>
    );
  }

  const isPermit =
    detail.alert_type === "ACCESS_AUTHORIZATION" ||
    Boolean(detail.evidence_pack?.permit_code);

  const isSecurity =
    detail.alert_type === "SECURITY_ALERT" ||
    detail.alert_type === "SECURITY_INTERCEPTION" ||
    detail.alert_type === "UNAUTHORIZED_ACCESS" ||
    detail.severity === "CRITICAL" ||
    detail.severity === "HIGH";

  const isGovernance =
    detail.alert_type.includes("APPROVAL") ||
    detail.alert_type.includes("GOVERNANCE");

  const handleExecutePermit = async () => {
    if (!detail.evidence_pack?.permit_code) return;
    const permitCode = detail.evidence_pack.permit_code;
    const action =
      detail.evidence_pack.tool_name?.split(" ")[0] || "operate_pump";
    const resource =
      detail.evidence_pack.tool_name?.match(/\[(.*?)\]/)?.[1] || "P-101A";

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
      onDetailUpdated();
    } catch (err: unknown) {
      setExecutionError(err instanceof Error ? err.message : "Execution denied.");
    } finally {
      setIsExecutingPermit(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col min-w-0 bg-surface-2/20 overflow-y-auto">
      <div className="p-4 md:p-6 space-y-5 max-w-4xl">
        {/* Mobile Back Button */}
        <div className="md:hidden pb-2 border-b border-surface-border flex items-center justify-between">
          <Button
            size="sm"
            variant="secondary"
            onClick={onBackMobile}
            className="text-xs"
          >
            ← Back to Messages
          </Button>
          <span className="font-mono text-[10px] text-ink-3">
            ID: #{detail.id}
          </span>
        </div>

        {/* Header */}
        <div className="border-b border-surface-border pb-4 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                className={`rounded px-2 py-0.5 font-mono text-[11px] font-bold uppercase ${getSeverityBadge(
                  detail.severity
                )}`}
              >
                {detail.severity}
              </span>
              <span className="rounded bg-surface-3 px-2 py-0.5 font-mono text-[11px] text-ink-3">
                {detail.alert_type}
              </span>
              <span className="font-mono text-[10px] text-ink-3">
                Mode: {detail.composition_mode}
              </span>
            </div>
            <div className="font-mono text-xs text-ink-3">
              {formatFullDateTime(detail.created_at)}
            </div>
          </div>

          <h2 className="text-lg font-bold text-ink-1">{detail.subject}</h2>

          <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-ink-3">
            <div>
              From: <span className="text-ink-1 font-semibold">{detail.sender}</span>
            </div>
            <div>
              To: <span className="text-ink-1">{detail.recipients.join(", ")}</span>
            </div>
            {detail.read_at && (
              <div>
                Read at: <span className="text-ink-2">{formatIstTime(detail.read_at)} IST</span>
              </div>
            )}
          </div>
        </div>

        {/* Specialized Message Viewers */}
        {isPermit && (
          <PermitMessageDetail
            detail={detail}
            role={role}
            isExecuting={isExecutingPermit}
            onRequestExecution={() => setShowConfirmModal(true)}
            executionResult={executionResult}
            executionError={executionError}
          />
        )}

        {!isPermit && isSecurity && <SecurityMessageDetail detail={detail} />}
        {!isPermit && !isSecurity && isGovernance && <GovernanceMessageDetail detail={detail} />}

        {/* View Mode Toggle: Sanitized HTML vs Plain text */}
        <div className="flex items-center justify-between border-b border-surface-border pb-1">
          <span className="font-mono text-xs font-bold uppercase tracking-wider text-ink-3">
            Message Content
          </span>
          <div className="flex items-center gap-1 rounded bg-surface-3 p-0.5">
            <button
              type="button"
              onClick={() => onToggleBodyViewMode("html")}
              className={`rounded px-2 py-0.5 text-xs font-mono transition-colors ${
                bodyViewMode === "html"
                  ? "bg-surface-1 font-bold text-ink-1 shadow"
                  : "text-ink-3 hover:text-ink-1"
              }`}
            >
              HTML
            </button>
            <button
              type="button"
              onClick={() => onToggleBodyViewMode("text")}
              className={`rounded px-2 py-0.5 text-xs font-mono transition-colors ${
                bodyViewMode === "text"
                  ? "bg-surface-1 font-bold text-ink-1 shadow"
                  : "text-ink-3 hover:text-ink-1"
              }`}
            >
              Plain Text
            </button>
          </div>
        </div>

        {/* Body Content Render */}
        {bodyViewMode === "html" && detail.body_html ? (
          <div className="rounded-lg border border-surface-border bg-white overflow-hidden text-black">
            <iframe
              title="Email Preview"
              srcDoc={detail.body_html}
              className="w-full h-80 border-0"
              sandbox="allow-same-origin"
            />
          </div>
        ) : (
          <div className="rounded-lg border border-surface-border bg-surface-1 p-4 font-mono text-xs leading-relaxed text-ink-1 whitespace-pre-wrap">
            {detail.body_text}
          </div>
        )}

        {/* Attachments Section */}
        {detail.attachments && detail.attachments.length > 0 && (
          <div className="rounded-lg border border-surface-border bg-surface-2/60 p-3 space-y-2">
            <div className="flex items-center gap-2 font-mono text-[11px] font-bold text-ink-2 uppercase tracking-wider">
              <IconDownload className="h-3.5 w-3.5 text-brand" />
              <span>Attached Files ({detail.attachments.length})</span>
            </div>
            {downloadError && (
              <p className="font-mono text-[10px] text-status-error">{downloadError}</p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {detail.attachments.map((att) => (
                <button
                  type="button"
                  key={att.id}
                  onClick={async () => {
                    try {
                      setDownloadError(null);
                      await mailApi.downloadAttachment(detail.id, att.id, att.filename);
                    } catch (err) {
                      setDownloadError(
                        err instanceof Error ? err.message : "Attachment download failed"
                      );
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

        {/* Verified Grounding Citations */}
        <div className="space-y-2">
          <h4 className="font-mono text-[11px] uppercase tracking-wider text-ink-3 font-bold">
            Authoritative Grounding Citations ({detail.citations?.length || 0})
          </h4>
          {!detail.citations || detail.citations.length === 0 ? (
            <p className="text-xs text-ink-3">No external citations attached.</p>
          ) : (
            <div className="space-y-2">
              {detail.citations.map((c) => (
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
        {detail.artifact && (
          <div className="rounded-lg border border-surface-border bg-surface-1 p-3 flex items-center justify-between">
            <div className="space-y-0.5">
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-3 font-bold block">
                Official Document Deliverable
              </span>
              <p className="text-xs font-semibold text-ink-1">{detail.artifact.filename}</p>
              <p className="font-mono text-[10px] text-ink-3 truncate">
                SHA256: {detail.artifact.sha256_hash.slice(0, 24)}... (
                {Math.round(detail.artifact.file_size / 1024)} KB)
              </p>
            </div>
            <a
              href={`/api/v1/workspaces/${workspaceId || 1}/artifacts/${detail.artifact.id}/download`}
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

      {/* Confirmation Modal */}
      {showConfirmModal && (
        <PermitConfirmModal
          detail={detail}
          isExecuting={isExecutingPermit}
          onConfirm={handleExecutePermit}
          onCancel={() => setShowConfirmModal(false)}
        />
      )}
    </div>
  );
}
