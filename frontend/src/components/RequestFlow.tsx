import { IconAlertTriangle, IconCheck, IconLock } from "@/components/ui/Icon";
import type { RunStatusSummary } from "@/types";

export function RequestFlow({ summary }: { summary: RunStatusSummary | null }) {
  if (!summary?.stages.length) return null;
  return (
    <section className="panel p-4" aria-label="Verified request flow">
      <div className="mb-3 flex items-center justify-between">
        <div><p className="text-xs font-mono font-semibold uppercase tracking-wider text-ink-1">What happened</p><p className="mt-1 text-[11px] text-ink-3">Live stages verified by the backend for run #{summary.run_id}</p></div>
        <span className="flex items-center gap-1 font-mono text-[10px] text-status-success"><IconLock className="h-3 w-3" /> BACKEND VERIFIED</span>
      </div>
      <div className="flex flex-wrap items-stretch gap-2">
        {summary.stages.map((stage, index) => (
          <div key={stage.key} className="contents">
            {index > 0 && <span className="self-center text-ink-3" aria-hidden="true">→</span>}
            <div className={`min-w-[150px] flex-1 rounded border p-2.5 ${stage.status === "complete" ? "border-status-success/30 bg-status-success/5" : "border-status-warning/40 bg-status-warning/5"}`}>
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wide text-ink-3">
                {stage.status === "complete" ? <IconCheck className="h-3 w-3 text-status-success" /> : <IconAlertTriangle className="h-3 w-3 text-status-warning" />}{stage.label}
              </div>
              <p className="mt-1 text-xs font-medium text-ink-1">{stage.value}</p>
              {stage.detail && <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-ink-3">{stage.detail}</p>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
