import { IconCheck } from "@/components/ui/Icon";
import type { MailMessageDetail } from "./types";

interface GovernanceMessageDetailProps {
  detail: MailMessageDetail;
}

export function GovernanceMessageDetail({ detail }: GovernanceMessageDetailProps) {
  return (
    <div className="rounded-xl border border-indigo-500/40 bg-indigo-500/5 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <IconCheck className="h-5 w-5 text-indigo-400" />
          <span className="font-mono text-xs font-bold uppercase tracking-wider text-indigo-300">
            Four-Eyes Governance Consensus
          </span>
        </div>
        <span className="rounded bg-indigo-500/20 px-2 py-0.5 font-mono text-[11px] font-bold text-indigo-300">
          DUAL-SUPERVISOR ENFORCED
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs font-mono">
        <div>
          <span className="text-ink-3 block">Protocol Type:</span>
          <span className="text-indigo-300 font-bold">{detail.alert_type}</span>
        </div>
        <div>
          <span className="text-ink-3 block">Originating Actor:</span>
          <span className="text-ink-1 font-bold">{detail.sender}</span>
        </div>
        <div>
          <span className="text-ink-3 block">Assigned Stakeholder:</span>
          <span className="text-ink-1 font-bold">{detail.related_user || "Supervisor Circle"}</span>
        </div>
      </div>

      <div className="rounded border border-surface-border bg-surface-1 p-2.5 text-[11px] font-mono text-ink-3">
        Compliance Requirement: High-consequence interventions mandate consensus across two distinct supervisor accounts before execution unlocks.
      </div>
    </div>
  );
}
