import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { authorizationsApi } from "@/api/authorizations";

interface PermitRequestModalProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId: number | null;
  onPermitRequested: () => void;
}

export function PermitRequestModal({
  isOpen,
  onClose,
  workspaceId,
  onPermitRequested,
}: PermitRequestModalProps) {
  const [requestAction, setRequestAction] = useState("operate_pump");
  const [requestResource, setRequestResource] = useState("P-101A");
  const [requestDuration, setRequestDuration] = useState(60);
  const [requestReason, setRequestReason] = useState(
    "Scheduled operational run under supervisor authorization"
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspaceId) return;
    setIsSubmitting(true);
    try {
      await authorizationsApi.create({
        workspace_id: workspaceId,
        action: requestAction,
        resource: requestResource,
        valid_duration_minutes: Number(requestDuration),
        reason: requestReason,
      });
      onClose();
      onPermitRequested();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Permit request failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-lg rounded-xl border border-surface-border bg-surface-1 p-6 space-y-4 shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <h3 className="font-bold text-base text-ink-1">Request Operational Work Permit</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-ink-3 hover:text-ink-1 text-sm font-bold"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3 text-xs">
          <div>
            <label className="block text-ink-3 font-mono mb-1 font-medium">
              Target Industrial Equipment
            </label>
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
            <label className="block text-ink-3 font-mono mb-1 font-medium">
              Requested Action / Tool
            </label>
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
            <label className="block text-ink-3 font-mono mb-1 font-medium">
              Validity Duration (Minutes)
            </label>
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
            <label className="block text-ink-3 font-mono mb-1 font-medium">
              Operational Justification / Reason
            </label>
            <textarea
              rows={2}
              value={requestReason}
              onChange={(e) => setRequestReason(e.target.value)}
              className="w-full rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-xs text-ink-1 font-mono focus:border-brand focus:outline-none"
              required
            />
          </div>

          <div className="rounded bg-surface-2 p-2.5 text-[11px] font-mono text-ink-3">
            Governance: This request will be submitted in <strong>PENDING_APPROVAL (0/2)</strong>. It requires two independent authenticated supervisor approvals before becoming active.
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-3 border-t border-surface-border">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Submitting..." : "Submit Permit Request"}
          </Button>
        </div>
      </form>
    </div>
  );
}
