import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import type { RunEvent } from "@/types";

function tagFor(eventType: string): { tag: string; className: string } {
  if (eventType.startsWith("retrieval")) {
    return { tag: "RAG", className: "text-status-knowledge bg-status-knowledge/10" };
  }
  if (eventType.startsWith("model_") || eventType.includes("prompt") || eventType.includes("response")) {
    return { tag: "LLM", className: "text-brand bg-brand/10" };
  }
  if (eventType.startsWith("tool_")) {
    return { tag: "TOOL", className: "text-status-info bg-status-info/10" };
  }
  if (eventType.includes("approval")) {
    return { tag: "HITL", className: "text-status-warning bg-status-warning/10 font-bold" };
  }
  if (eventType.includes("classified") || eventType.includes("routing") || eventType.includes("route")) {
    return { tag: "ROUTE", className: "text-status-knowledge bg-status-knowledge/10" };
  }
  if (eventType === "completed" || eventType.includes("completed")) {
    return { tag: "DONE", className: "text-status-success bg-status-success/10 font-bold" };
  }
  if (eventType.includes("failed") || eventType.includes("error")) {
    return { tag: "ERR", className: "text-status-error bg-status-error/10 font-bold" };
  }
  return { tag: "SYS", className: "text-ink-2 bg-surface-3" };
}

export function EventTimeline({ events }: { events: RunEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="py-1 text-xs italic text-ink-3">
        // System standing by. Dispatch a query to observe the reasoning trace…
      </div>
    );
  }

  return (
    <div className="space-y-1.5 font-mono text-xs">
      {events.map((event) => {
        const { tag, className } = tagFor(event.event_type);
        return (
          <div key={event.id} className="flex items-start gap-2 py-0.5">
            <span
              className={cn("shrink-0 select-none rounded px-1 py-0.5 text-[9px] font-bold", className)}
            >
              {tag}
            </span>
            <span className="text-ink-2">{event.message ?? event.event_type}</span>
            <span className="ml-auto shrink-0 pl-2 text-[10px] text-ink-3">
              {formatDateTime(event.created_at)}
            </span>
          </div>
        );
      })}
    </div>
  );
}