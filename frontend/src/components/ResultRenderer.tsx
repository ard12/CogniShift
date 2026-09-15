import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Badge } from "@/components/ui/Badge";
import { IconCheck, IconAlertTriangle, IconActivity } from "@/components/ui/Icon";

interface ResultRendererProps {
  content: string;
  confidence?: number | null;
  modelName?: string | null;
  operatingMode?: string | null;
  routingInfo?: Record<string, unknown> | null;
}

interface ParsedRCAHeader {
  isRCA: boolean;
  statusLabel?: string;
  statusTone?: "success" | "warning" | "danger" | "info" | "neutral";
  targetAsset?: string;
  causeCode?: string;
  confidencePercent?: number;
}

export function ResultRenderer({
  content,
  confidence,
  modelName,
  operatingMode,
}: ResultRendererProps) {
  // Check if output represents a Root Cause Analysis response
  const rcaHeader = useMemo<ParsedRCAHeader>(() => {
    if (!content) return { isRCA: false };
    const lower = content.toLowerCase();
    const isRcaMatch =
      lower.includes("root cause analysis") ||
      lower.includes("rca evidence bundle") ||
      lower.includes("target asset & operational status") ||
      lower.includes("physical primary cause");

    if (!isRcaMatch) return { isRCA: false };

    let statusLabel = "RCA Investigation";
    let statusTone: "success" | "warning" | "danger" | "info" | "neutral" = "info";

    if (lower.includes("confirmed cause") || lower.includes("status: confirmed_cause")) {
      statusLabel = "CONFIRMED CAUSE";
      statusTone = "success";
    } else if (lower.includes("supported likely cause") || lower.includes("status: supported_likely_cause")) {
      statusLabel = "SUPPORTED LIKELY CAUSE";
      statusTone = "info";
    } else if (lower.includes("plausible hypothesis") || lower.includes("status: plausible_hypothesis")) {
      statusLabel = "PLAUSIBLE HYPOTHESIS";
      statusTone = "warning";
    } else if (lower.includes("insufficient evidence") || lower.includes("status: insufficient_evidence")) {
      statusLabel = "INSUFFICIENT EVIDENCE";
      statusTone = "danger";
    } else if (lower.includes("contradictory") || lower.includes("status: contradictory_evidence")) {
      statusLabel = "CONTRADICTORY EVIDENCE";
      statusTone = "danger";
    }

    // Extract asset tag e.g. P-101A, K-101, FV-302, R-301
    const assetMatch = content.match(/\b([A-Z]{1,4}-\d{2,4}[A-Z]?)\b/);
    const targetAsset = assetMatch ? assetMatch[1] : undefined;

    // Extract cause code e.g. MEC_PUMP_CAVITATION, INST_SENSOR_DRIFT, ELEC_MOTOR_OVERHEAT
    const causeMatch = content.match(/\b([A-Z]{3,4}_[A-Z0-9_]{4,30})\b/);
    const causeCode = causeMatch ? causeMatch[1] : undefined;

    const confVal = confidence !== null && confidence !== undefined ? Math.round(confidence * 100) : undefined;

    return {
      isRCA: true,
      statusLabel,
      statusTone,
      targetAsset,
      causeCode,
      confidencePercent: confVal,
    };
  }, [content, confidence]);

  if (!content) {
    return (
      <div className="rounded border border-surface-border bg-surface-1 p-4 text-sm text-ink-3 italic">
        No response generated yet.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-border/60 pb-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold uppercase tracking-wider text-ink-1">
            {rcaHeader.isRCA ? "Root Cause Analysis (Section 17 Protocol)" : "Operational Synthesis"}
          </span>
          {rcaHeader.isRCA && rcaHeader.statusLabel && (
            <Badge tone={rcaHeader.statusTone || "info"} className="font-mono text-[10px] font-bold">
              {rcaHeader.statusLabel}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono text-ink-3">
          {confidence !== null && confidence !== undefined && (
            <span className="rounded bg-surface-3 px-1.5 py-0.5 font-semibold text-ink-2">
              Confidence: {(confidence * 100).toFixed(0)}%
            </span>
          )}
          {modelName && (
            <span className="text-ink-3">
              {operatingMode?.toLowerCase() === "local" ? "SOVEREIGN LOCAL" : "INFERENCE"}: {modelName.toUpperCase()}
            </span>
          )}
        </div>
      </div>

      {/* RCA Metadata Summary Card if active */}
      {rcaHeader.isRCA && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 rounded-lg border border-brand/30 bg-brand/5 p-3 text-xs font-mono">
          {rcaHeader.targetAsset && (
            <div className="flex items-center gap-2">
              <IconActivity className="h-4 w-4 text-brand shrink-0" />
              <div>
                <span className="text-[10px] text-ink-3 uppercase block">Target Equipment</span>
                <span className="font-bold text-ink-1 text-sm">{rcaHeader.targetAsset}</span>
              </div>
            </div>
          )}
          {rcaHeader.causeCode && (
            <div className="flex items-center gap-2">
              <IconAlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
              <div>
                <span className="text-[10px] text-ink-3 uppercase block">Verified Cause Code</span>
                <span className="font-bold text-amber-300">{rcaHeader.causeCode}</span>
              </div>
            </div>
          )}
          {rcaHeader.confidencePercent !== undefined && (
            <div className="flex items-center gap-2">
              <IconCheck className="h-4 w-4 text-emerald-400 shrink-0" />
              <div>
                <span className="text-[10px] text-ink-3 uppercase block">Diagnosis Confidence</span>
                <span className="font-bold text-emerald-300">{rcaHeader.confidencePercent}%</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Markdown Body with GFM Tables */}
      <div className="markdown-prose text-sm leading-relaxed text-ink-1">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            table: ({ ...props }) => (
              <div className="my-3 overflow-x-auto rounded-md border border-surface-border bg-surface-1 shadow-sm">
                <table className="w-full border-collapse text-left font-mono text-xs" {...props} />
              </div>
            ),
            thead: ({ ...props }) => (
              <thead className="border-b border-surface-border bg-surface-3/70 font-semibold uppercase tracking-wider text-ink-1" {...props} />
            ),
            th: ({ ...props }) => (
              <th className="px-3 py-2.5 border-r border-surface-border/40 last:border-r-0" {...props} />
            ),
            td: ({ ...props }) => (
              <td className="border-b border-surface-border/40 px-3 py-2 border-r border-surface-border/20 last:border-r-0 text-ink-2" {...props} />
            ),
            tr: ({ ...props }) => (
              <tr className="hover:bg-surface-2/40 transition-colors" {...props} />
            ),
            h1: ({ ...props }) => (
              <h1 className="mt-4 mb-2 font-mono text-base font-bold text-ink-1 border-b border-surface-border/60 pb-1" {...props} />
            ),
            h2: ({ ...props }) => (
              <h2 className="mt-3.5 mb-1.5 font-mono text-sm font-bold text-brand uppercase tracking-wide" {...props} />
            ),
            h3: ({ ...props }) => (
              <h3 className="mt-3 mb-1 font-mono text-xs font-bold text-ink-1 uppercase tracking-wider" {...props} />
            ),
            p: ({ ...props }) => (
              <p className="my-1.5 leading-relaxed text-ink-1" {...props} />
            ),
            ul: ({ ...props }) => (
              <ul className="my-2 list-disc space-y-1 pl-5 text-ink-1 text-xs" {...props} />
            ),
            ol: ({ ...props }) => (
              <ol className="my-2 list-decimal space-y-1 pl-5 text-ink-1 text-xs" {...props} />
            ),
            li: ({ ...props }) => (
              <li className="leading-relaxed" {...props} />
            ),
            code: ({ className, children, ...props }) => {
              const isInline = !className && typeof children === "string" && !children.includes("\n");
              return isInline ? (
                <code className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11px] font-medium text-brand border border-surface-border/40" {...props}>
                  {children}
                </code>
              ) : (
                <div className="my-2.5 overflow-x-auto rounded-md border border-surface-border bg-black/40 p-3">
                  <code className="font-mono text-xs leading-normal text-emerald-300" {...props}>
                    {children}
                  </code>
                </div>
              );
            },
            blockquote: ({ ...props }) => (
              <blockquote className="my-2.5 border-l-2 border-brand bg-brand/5 pl-3 py-1 italic text-xs text-ink-2" {...props} />
            ),
            strong: ({ ...props }) => (
              <strong className="font-semibold text-ink-1" {...props} />
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
