import { Button } from "@/components/ui/Button";
import { IconAlertTriangle, IconCheck, IconPlay, IconShieldCheck } from "@/components/ui/Icon";
import type { MailMessageDetail, ExecutionResult } from "./types";

interface PermitMessageDetailProps {
  detail: MailMessageDetail;
  role: string | null;
  isExecuting: boolean;
  onRequestExecution: () => void;
  executionResult: ExecutionResult | null;
  executionError: string | null;
}

export function PermitMessageDetail({
  detail,
  role,
  isExecuting,
  onRequestExecution,
  executionResult,
  executionError,
}: PermitMessageDetailProps) {
  const isConsumed = detail.alert_type === "AUTHORIZATION_CONSUMED";
  const permitCode = detail.evidence_pack?.permit_code || "ACTIVE";
  const equipment =
    detail.evidence_pack?.tool_name?.match(/\[(.*?)\]/)?.[1] || "P-101A";
  const action =
    detail.evidence_pack?.tool_name?.split(" ")[0] || "operate_pump";

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-brand/40 bg-brand/5 p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <IconShieldCheck className="h-5 w-5 text-brand" />
            <span className="font-mono text-xs font-bold uppercase tracking-wider text-brand">
              Operational Work Permit Notice
            </span>
          </div>
          <span className="rounded bg-brand/20 px-2 py-0.5 font-mono text-[11px] font-bold text-brand">
            {permitCode}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs font-mono">
          <div>
            <span className="text-ink-3 block">Authorized User:</span>
            <span className="text-brand font-bold">
              {detail.related_user || role || "operator"}
            </span>
          </div>
          <div>
            <span className="text-ink-3 block">Target Asset:</span>
            <span className="text-ink-1 font-bold">{equipment}</span>
          </div>
          <div>
            <span className="text-ink-3 block">Action Scope:</span>
            <span className="text-ink-1 font-bold">{action}</span>
          </div>
          <div>
            <span className="text-ink-3 block">Permitted Uses:</span>
            <span className="text-ink-1 font-bold">
              {isConsumed ? "0 / 1 (CONSUMED)" : "1 / 1 (READY)"}
            </span>
          </div>
        </div>

        {/* EXECUTION ACTION BUTTON */}
        <div className="pt-2 border-t border-brand/20 flex flex-wrap items-center justify-between gap-2">
          <div className="text-[11px] text-ink-3 font-mono">
            [SIMULATED INDUSTRIAL ACTION - SIH FINALS PROTOTYPE]
          </div>
          {isConsumed ? (
            <span className="rounded border border-surface-border bg-surface-3 px-3 py-1 text-xs font-mono font-bold text-ink-3">
              PERMIT CONSUMED (Uses Expended)
            </span>
          ) : (
            <Button
              size="sm"
              variant="success"
              disabled={isExecuting}
              onClick={onRequestExecution}
            >
              <IconPlay className="h-3.5 w-3.5 mr-1" />
              Execute Authorized Action (Simulated)
            </Button>
          )}
        </div>
      </div>

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
    </div>
  );
}
