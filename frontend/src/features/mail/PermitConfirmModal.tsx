import { Button } from "@/components/ui/Button";
import { IconAlertTriangle } from "@/components/ui/Icon";
import type { MailMessageDetail } from "./types";

interface PermitConfirmModalProps {
  detail: MailMessageDetail;
  isExecuting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function PermitConfirmModal({
  detail,
  isExecuting,
  onConfirm,
  onCancel,
}: PermitConfirmModalProps) {
  const permitCode = detail.evidence_pack?.permit_code || "ACTIVE";
  const equipment =
    detail.evidence_pack?.tool_name?.match(/\[(.*?)\]/)?.[1] || "P-101A";
  const action =
    detail.evidence_pack?.tool_name?.split(" ")[0] || "operate_pump";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-surface-border bg-surface-1 p-6 space-y-4 shadow-2xl">
        <div className="flex items-center gap-2.5 text-status-warning">
          <IconAlertTriangle className="h-5 w-5" />
          <h3 className="font-bold text-base text-ink-1">Confirm Operational Execution</h3>
        </div>

        <div className="rounded-lg border border-surface-border bg-surface-2 p-3 text-xs font-mono space-y-1.5">
          <div>
            <span className="text-ink-3">Permit Code:</span>{" "}
            <span className="text-brand font-bold">{permitCode}</span>
          </div>
          <div>
            <span className="text-ink-3">Equipment:</span>{" "}
            <span className="text-ink-1 font-semibold">{equipment}</span>
          </div>
          <div>
            <span className="text-ink-3">Action:</span>{" "}
            <span className="text-ink-1 font-semibold">{action}</span>
          </div>
          <div>
            <span className="text-ink-3">Remaining Uses:</span>{" "}
            <span className="text-ink-1 font-semibold">1 (Single-Use Permit)</span>
          </div>
        </div>

        <div className="rounded bg-status-warning/10 border border-status-warning/30 p-2.5 text-[11px] font-mono text-status-warning leading-relaxed">
          [SIMULATED INDUSTRIAL ACTION - SIH FINALS PROTOTYPE]
          <br />
          This action will atomically consume this one-time permit. A second execution attempt will fail closed.
        </div>

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-surface-border">
          <Button variant="secondary" onClick={onCancel} disabled={isExecuting}>
            Cancel
          </Button>
          <Button variant="success" onClick={onConfirm} disabled={isExecuting}>
            {isExecuting ? "Executing..." : "Execute & Consume Permit"}
          </Button>
        </div>
      </div>
    </div>
  );
}
