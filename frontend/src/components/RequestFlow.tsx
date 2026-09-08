import { IconAlertTriangle, IconCheck, IconLock } from "@/components/ui/Icon";
import type { RunStatusSummary } from "@/types";

export function RequestFlow({ summary }: { summary: RunStatusSummary | null }) {
  if (!summary?.stages.length) return null;
  return (
    <section className="panel p-4" aria-label="Verified request flow">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div><p className="text-xs font-mono font-semibold uppercase tracking-wider text-ink-1">What happened</p><p className="mt-1 text-[11px] text-ink-3">Live stages verified by the backend for run #{summary.run_id}</p></div>
        <span className="flex shrink-0 items-center gap-1 font-mono text-[10px] text-status-success"><IconLock className="h-3 w-3" /> BACKEND VERIFIED</span>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(165px,1fr))] gap-2">
        {summary.stages.map((stage, index) => {
          const values = stage.key === "source" ? stage.value.split(/,\s+/) : [stage.value];
          return (
            <div key={stage.key} className={`relative min-w-0 rounded border p-2.5 ${stage.status === "complete" ? "border-status-success/30 bg-status-success/5" : "border-status-warning/40 bg-status-warning/5"}`}>
              <span className="absolute right-2 top-2 font-mono text-[9px] text-ink-3/60" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wide text-ink-3">
                {stage.status === "complete" ? <IconCheck className="h-3 w-3 text-status-success" /> : <IconAlertTriangle className="h-3 w-3 text-status-warning" />}{stage.label}
              </div>
              <div className="mt-1 space-y-0.5">
                {values.map((value) => <p key={value} className={`${stage.key === "source" ? "break-all" : "break-words"} text-xs font-medium leading-4 text-ink-1`}>{value}</p>)}
              </div>
              {stage.detail && <p className="mt-1 line-clamp-2 break-words text-[10px] leading-4 text-ink-3">{stage.detail}</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
