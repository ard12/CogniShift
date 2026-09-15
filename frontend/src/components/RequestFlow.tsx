import { IconAlertTriangle, IconCheck, IconLock, IconLoader } from "@/components/ui/Icon";
import type { RunStatusSummary } from "@/types";

interface RequestFlowProps {
  summary: RunStatusSummary | null;
  isExecuting?: boolean;
  activeStage?: string | null;
}

const PIPELINE_STAGES = [
  { id: "route", title: "1. Intent & Policy Gate", desc: "Semantic routing & air-gap scope validation" },
  { id: "rag", title: "2. Multimodal Substrate", desc: "FastEmbed, ColModernVBERT & topology lookup" },
  { id: "engine", title: "3. Reasoning & Sandbox", desc: "Multi-turn state machine & tool interlocks" },
  { id: "synthesis", title: "4. Section 17 Protocol", desc: "Provenance verification & artifact generation" },
];

export function RequestFlow({ summary, isExecuting, activeStage }: RequestFlowProps) {
  if (isExecuting) {
    return (
      <section className="panel p-4" aria-label="Executing request flow">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs font-mono font-semibold uppercase tracking-wider text-ink-1">
              Active Sovereign Execution Pipeline
            </p>
            <p className="mt-0.5 text-[11px] text-ink-3">
              {activeStage || "Real-time engine execution in progress across on-premise models…"}
            </p>
          </div>
          <span className="flex shrink-0 items-center gap-1.5 font-mono text-[10px] text-brand">
            <span className="inline-block h-2 w-2 rounded-full bg-brand animate-ping" />
            LIVE INFERENCE
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {PIPELINE_STAGES.map((st, idx) => (
            <div
              key={st.id}
              className="relative min-w-0 rounded-lg border border-brand/30 bg-surface-2/60 p-3 flex flex-col justify-between"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-mono text-[10px] text-brand font-bold uppercase tracking-wider">
                  {st.title}
                </span>
                <IconLoader className="h-3 w-3 animate-spin text-brand/70" />
              </div>
              <p className="text-[11px] text-ink-2 leading-snug">{st.desc}</p>
              <div className="mt-2 h-1 w-full rounded-full bg-surface-3 overflow-hidden">
                <div
                  className="h-full bg-brand rounded-full animate-pulse"
                  style={{ width: `${(idx + 1) * 25}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (!summary?.stages.length) return null;

  return (
    <section className="panel p-4" aria-label="Verified request flow">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-mono font-semibold uppercase tracking-wider text-ink-1">
            What happened
          </p>
          <p className="mt-1 text-[11px] text-ink-3">
            Live stages verified by the backend for run #{summary.run_id}
          </p>
        </div>
        <span className="flex shrink-0 items-center gap-1 font-mono text-[10px] text-status-success">
          <IconLock className="h-3 w-3" /> BACKEND VERIFIED
        </span>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(165px,1fr))] gap-2">
        {summary.stages.map((stage, index) => {
          const values = stage.key === "source" ? stage.value.split(/,\s+/) : [stage.value];
          return (
            <div
              key={stage.key}
              className={`relative min-w-0 rounded border p-2.5 ${
                stage.status === "complete"
                  ? "border-status-success/30 bg-status-success/5"
                  : "border-status-warning/40 bg-status-warning/5"
              }`}
            >
              <span
                className="absolute right-2 top-2 font-mono text-[9px] text-ink-3/60"
                aria-hidden="true"
              >
                {String(index + 1).padStart(2, "0")}
              </span>
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wide text-ink-3">
                {stage.status === "complete" ? (
                  <IconCheck className="h-3 w-3 text-status-success" />
                ) : (
                  <IconAlertTriangle className="h-3 w-3 text-status-warning" />
                )}
                {stage.label}
              </div>
              <div className="mt-1 space-y-0.5">
                {values.map((value) => (
                  <p
                    key={value}
                    className={`${
                      stage.key === "source" ? "break-all" : "break-words"
                    } text-xs font-medium leading-4 text-ink-1`}
                  >
                    {value}
                  </p>
                ))}
              </div>
              {stage.detail && (
                <p className="mt-1 line-clamp-2 break-words text-[10px] leading-4 text-ink-3">
                  {stage.detail}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
