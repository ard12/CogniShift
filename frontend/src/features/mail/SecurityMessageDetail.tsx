import { IconAlertTriangle } from "@/components/ui/Icon";
import type { MailMessageDetail } from "./types";

interface SecurityMessageDetailProps {
  detail: MailMessageDetail;
}

export function SecurityMessageDetail({ detail }: SecurityMessageDetailProps) {
  return (
    <div className="rounded-xl border border-status-warning/40 bg-status-warning/5 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <IconAlertTriangle className="h-5 w-5 text-status-warning" />
          <span className="font-mono text-xs font-bold uppercase tracking-wider text-status-warning">
            Sovereign Security Audit Event
          </span>
        </div>
        <span className="rounded bg-status-warning/20 px-2 py-0.5 font-mono text-[11px] font-bold text-status-warning">
          {detail.alert_type}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs font-mono">
        <div>
          <span className="text-ink-3 block">Severity Level:</span>
          <span className="text-status-warning font-bold">{detail.severity}</span>
        </div>
        <div>
          <span className="text-ink-3 block">Incident Source:</span>
          <span className="text-ink-1 font-bold">{detail.sender}</span>
        </div>
        <div>
          <span className="text-ink-3 block">Audit Target:</span>
          <span className="text-ink-1 font-bold">{detail.related_user || "System Layer"}</span>
        </div>
      </div>

      <div className="rounded border border-surface-border bg-surface-1 p-2.5 text-[11px] font-mono text-ink-3">
        Local sovereign execution with no public-cloud AI/model dependency in the demonstrated workflow.
      </div>
    </div>
  );
}
