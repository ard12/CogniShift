import { useState, useMemo } from "react";
import { cn } from "@/lib/cn";
import { formatDateTime, formatIstTime, parseUtcDate } from "@/lib/format";
import type { RunEvent } from "@/types";
import {
  IconChevronDown,
  IconChevronRight,
  IconCopy,
  IconCheck,
  IconFileText,
  IconTerminal,
  IconX,
  IconShieldCheck,
} from "@/components/ui/Icon";

type FilterCategory = "all" | "rag" | "tool" | "synthesis" | "governance";

function tagFor(eventType: string): { tag: string; className: string; borderClass: string } {
  if (eventType.startsWith("retrieval")) {
    return {
      tag: "RAG",
      className: "text-status-knowledge bg-status-knowledge/10",
      borderClass: "border-status-knowledge/40",
    };
  }
  if (eventType.startsWith("model_") || eventType.includes("prompt") || eventType.includes("response")) {
    return {
      tag: "LLM",
      className: "text-brand bg-brand/10",
      borderClass: "border-brand/40",
    };
  }
  if (eventType.startsWith("tool_")) {
    return {
      tag: "TOOL",
      className: "text-status-info bg-status-info/10",
      borderClass: "border-status-info/40",
    };
  }
  if (eventType.includes("approval")) {
    return {
      tag: "HITL",
      className: "text-status-warning bg-status-warning/10 font-bold",
      borderClass: "border-status-warning/40",
    };
  }
  if (eventType.includes("classified") || eventType.includes("routing") || eventType.includes("route")) {
    return {
      tag: "ROUTE",
      className: "text-status-knowledge bg-status-knowledge/10",
      borderClass: "border-status-knowledge/40",
    };
  }
  if (eventType === "completed" || eventType.includes("completed")) {
    return {
      tag: "DONE",
      className: "text-status-success bg-status-success/10 font-bold",
      borderClass: "border-status-success/40",
    };
  }
  if (eventType.includes("failed") || eventType.includes("error")) {
    return {
      tag: "ERR",
      className: "text-status-error bg-status-error/10 font-bold",
      borderClass: "border-status-error/40",
    };
  }
  return {
    tag: "SYS",
    className: "text-ink-2 bg-surface-3",
    borderClass: "border-surface-border",
  };
}

function categorizeEvent(eventType: string): FilterCategory {
  if (eventType.startsWith("retrieval")) return "rag";
  if (eventType.startsWith("tool_")) return "tool";
  if (eventType === "completed" || eventType.includes("completed") || eventType.includes("approval")) {
    return "governance";
  }
  return "synthesis";
}

function formatLabel(key: string): string {
  const map: Record<string, string> = {
    pdf_qa: "PDF Acceptance Gate",
    docx_qa: "DOCX Acceptance Gate",
    pptx_qa: "PPTX Acceptance Gate",
    standards_grounding: "Governed Standards Compliance",
    visual_qa: "Visual Readability & Headroom",
    deliverables_count: "Deliverables Generated",
    peak_pressure: "Peak Excursion Pressure",
    asme_limit: "ASME VIII Design Limit",
    duration_above_limit: "Excursion Duration Over Limit",
    nominal_wt: "Nominal Wall Thickness",
    measured_wt: "Measured UT Thickness",
    min_required_wt: "Minimum Required Thickness",
    corrosion_status: "Corrosion Integrity",
    primary_cause: "Identified Root Cause",
    closure_time: "Observed Stroke Time",
    safeguard_action: "Safety Safeguard Action",
    valve_tag: "Asset Tag",
    source: "Telemetry File",
    chart_type: "Visualization Type",
    dimensions: "Render Resolution",
    governance: "Governance Framework",
  };
  if (map[key]) return map[key];
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function parseData(structuredData?: string | null): Record<string, unknown> | null {
  if (!structuredData) return null;
  try {
    const parsed = JSON.parse(structuredData);
    if (parsed && typeof parsed === "object") return parsed as Record<string, unknown>;
    return { value: parsed };
  } catch {
    return { raw: structuredData };
  }
}

function StatusValueBadge({ value }: { value: string }) {
  const v = value.toUpperCase();
  if (v === "ACCEPTED" || v === "VERIFIED" || v === "SATISFACTORY" || v.startsWith("PASS") || v === "TRUE") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-status-success/15 px-1.5 py-0.5 text-[10px] font-bold text-status-success border border-status-success/30 font-mono">
        <IconShieldCheck className="h-3 w-3" />
        {value}
      </span>
    );
  }
  if (v === "CRITICAL" || v.startsWith("FAIL") || v === "FALSE") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-status-error/15 px-1.5 py-0.5 text-[10px] font-bold text-status-error border border-status-error/30 font-mono">
        {value}
      </span>
    );
  }
  if (v.includes("WARN") || v.includes("DELAY")) {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-status-warning/15 px-1.5 py-0.5 text-[10px] font-bold text-status-warning border border-status-warning/30 font-mono">
        {value}
      </span>
    );
  }
  return <span className="font-mono text-ink-1 text-xs font-semibold">{value}</span>;
}

export function EventTimeline({
  events,
  runId,
}: {
  events: RunEvent[];
  runId?: number | string;
}) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [activeCategory, setActiveCategory] = useState<FilterCategory>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [rawViewIds, setRawViewIds] = useState<Set<number>>(new Set());
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [showFullAuditModal, setShowFullAuditModal] = useState(false);
  const [copiedAll, setCopiedAll] = useState(false);

  // Compute baseline timestamp for relative timing delta
  const baselineTime = useMemo(() => {
    if (events.length === 0) return 0;
    const firstDate = parseUtcDate(events[0].created_at);
    return firstDate ? firstDate.getTime() : 0;
  }, [events]);

  const categoryCounts = useMemo(() => {
    const counts = { all: events.length, rag: 0, tool: 0, synthesis: 0, governance: 0 };
    for (const e of events) {
      const cat = categorizeEvent(e.event_type);
      counts[cat]++;
    }
    return counts;
  }, [events]);

  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      if (activeCategory !== "all" && categorizeEvent(e.event_type) !== activeCategory) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const inMsg = (e.message ?? "").toLowerCase().includes(q);
        const inType = e.event_type.toLowerCase().includes(q);
        const inData = (e.structured_data ?? "").toLowerCase().includes(q);
        return inMsg || inType || inData;
      }
      return true;
    });
  }, [events, activeCategory, searchQuery]);

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleExpandAll = () => {
    if (expandedIds.size === filteredEvents.length && filteredEvents.length > 0) {
      setExpandedIds(new Set());
    } else {
      setExpandedIds(new Set(filteredEvents.map((e) => e.id)));
    }
  };

  const toggleRawMode = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setRawViewIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const copyEventJson = (event: RunEvent, e: React.MouseEvent) => {
    e.stopPropagation();
    const payload = {
      id: event.id,
      run_id: event.run_id,
      event_type: event.event_type,
      message: event.message,
      structured_data: parseData(event.structured_data),
      created_at: event.created_at,
    };
    void navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setCopiedId(event.id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const copyAllAuditTrail = () => {
    const fullTrace = events.map((e) => ({
      id: e.id,
      run_id: e.run_id,
      event_type: e.event_type,
      message: e.message,
      structured_data: parseData(e.structured_data),
      created_at: e.created_at,
    }));
    void navigator.clipboard.writeText(JSON.stringify(fullTrace, null, 2));
    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 2000);
  };

  if (events.length === 0) {
    return (
      <div className="py-4 text-center font-mono text-xs italic text-ink-3">
        // System standing by. Dispatch a query to observe the reasoning trace…
      </div>
    );
  }

  const allExpanded = filteredEvents.length > 0 && expandedIds.size === filteredEvents.length;

  return (
    <div className="flex flex-col gap-2 font-mono text-xs">
      {/* 1. Global Toolbar: Category Filters, Search, Expand All & Audit Stream */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-border/70 pb-2.5">
        <div className="flex items-center gap-1 overflow-x-auto py-0.5">
          <button
            type="button"
            onClick={() => setActiveCategory("all")}
            className={cn(
              "rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider transition",
              activeCategory === "all"
                ? "bg-surface-3 text-ink-1 border border-surface-border"
                : "text-ink-3 hover:text-ink-2 hover:bg-surface-2"
            )}
          >
            All ({categoryCounts.all})
          </button>
          {categoryCounts.rag > 0 && (
            <button
              type="button"
              onClick={() => setActiveCategory("rag")}
              className={cn(
                "rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider transition",
                activeCategory === "rag"
                  ? "bg-status-knowledge/20 text-status-knowledge border border-status-knowledge/40"
                  : "text-ink-3 hover:text-status-knowledge hover:bg-surface-2"
              )}
            >
              RAG ({categoryCounts.rag})
            </button>
          )}
          {categoryCounts.tool > 0 && (
            <button
              type="button"
              onClick={() => setActiveCategory("tool")}
              className={cn(
                "rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider transition",
                activeCategory === "tool"
                  ? "bg-status-info/20 text-status-info border border-status-info/40"
                  : "text-ink-3 hover:text-status-info hover:bg-surface-2"
              )}
            >
              Tools ({categoryCounts.tool})
            </button>
          )}
          {categoryCounts.synthesis > 0 && (
            <button
              type="button"
              onClick={() => setActiveCategory("synthesis")}
              className={cn(
                "rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider transition",
                activeCategory === "synthesis"
                  ? "bg-brand/20 text-brand border border-brand/40"
                  : "text-ink-3 hover:text-brand hover:bg-surface-2"
              )}
            >
              Synthesis ({categoryCounts.synthesis})
            </button>
          )}
          {categoryCounts.governance > 0 && (
            <button
              type="button"
              onClick={() => setActiveCategory("governance")}
              className={cn(
                "rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider transition",
                activeCategory === "governance"
                  ? "bg-status-success/20 text-status-success border border-status-success/40"
                  : "text-ink-3 hover:text-status-success hover:bg-surface-2"
              )}
            >
              QA Gate ({categoryCounts.governance})
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Search trace parameters…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-6 w-36 sm:w-44 rounded border border-surface-border bg-surface-2 px-2 text-[10px] font-mono text-ink-1 placeholder:text-ink-3/70 focus:border-brand focus:outline-none transition"
          />

          <button
            type="button"
            onClick={handleExpandAll}
            className="flex items-center gap-1 rounded border border-surface-border bg-surface-2 px-2 py-0.5 text-[10px] font-mono text-ink-2 hover:bg-surface-3 hover:text-ink-1 transition"
            title={allExpanded ? "Collapse all trace events" : "Expand all trace details"}
          >
            {allExpanded ? <IconChevronDown className="h-3 w-3" /> : <IconChevronRight className="h-3 w-3" />}
            <span>{allExpanded ? "Collapse All" : "Expand All"}</span>
          </button>

          <button
            type="button"
            onClick={() => setShowFullAuditModal(true)}
            className="flex items-center gap-1 rounded border border-brand/30 bg-brand/10 px-2 py-0.5 text-[10px] font-mono text-brand hover:bg-brand/20 transition"
            title="Inspect raw sovereign JSON audit trail"
          >
            <IconTerminal className="h-3 w-3" />
            <span>Raw Audit Trail</span>
          </button>
        </div>
      </div>

      {/* 2. Interactive Event Accordion List */}
      <div className="space-y-1.5">
        {filteredEvents.map((event, index) => {
          const { tag, className, borderClass } = tagFor(event.event_type);
          const isExpanded = expandedIds.has(event.id);
          const isRawMode = rawViewIds.has(event.id);
          const parsedData = parseData(event.structured_data);
          const hasData = parsedData !== null && Object.keys(parsedData).length > 0;
          const paramCount = hasData ? Object.keys(parsedData).length : 0;

          // Calculate relative timing
          const eventDate = parseUtcDate(event.created_at);
          const eventTime = eventDate ? eventDate.getTime() : 0;
          const deltaSec = baselineTime && eventTime ? ((eventTime - baselineTime) / 1000).toFixed(2) : "0.00";
          const preciseTime = eventDate ? formatIstTime(event.created_at) : formatDateTime(event.created_at);

          return (
            <div
              key={event.id}
              className={cn(
                "rounded border transition",
                isExpanded
                  ? cn("bg-surface-2/60 border-surface-border shadow-sm", borderClass)
                  : "border-surface-border/40 bg-surface-1/40 hover:bg-surface-2/40 hover:border-surface-border"
              )}
            >
              {/* Event Header Row (Always Clickable) */}
              <div
                className="flex items-center gap-2 px-2.5 py-1.5 cursor-pointer select-none"
                onClick={() => toggleExpand(event.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    toggleExpand(event.id);
                  }
                }}
                aria-expanded={isExpanded}
              >
                <span className="text-ink-3 hover:text-ink-1 transition shrink-0">
                  {isExpanded ? (
                    <IconChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <IconChevronRight className="h-3.5 w-3.5" />
                  )}
                </span>

                <span
                  className={cn(
                    "shrink-0 select-none rounded px-1.5 py-0.5 text-[9px] font-bold tracking-wider",
                    className
                  )}
                >
                  {tag}
                </span>

                <span className="text-ink-1 font-medium truncate flex-1">
                  {event.message ?? event.event_type}
                </span>

                {hasData && (
                  <span className="hidden sm:inline-flex shrink-0 items-center rounded bg-surface-3 px-1.5 py-0.5 text-[9px] font-mono text-ink-3 border border-surface-border/60">
                    &#123;&#125; {paramCount} {paramCount === 1 ? "param" : "params"}
                  </span>
                )}

                <span className="shrink-0 text-[10px] font-mono text-ink-3">
                  {preciseTime}
                </span>

                <span className="shrink-0 text-[9px] font-mono text-ink-3/70 bg-surface-3/50 px-1 py-0.5 rounded border border-surface-border/40">
                  +{deltaSec}s
                </span>
              </div>

              {/* 3. Deep Dive Expanded Drawer */}
              {isExpanded && (
                <div className="border-t border-surface-border/60 bg-surface-0/60 p-3 space-y-2.5">
                  {/* Metadata & Controls Bar */}
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-ink-3 border-b border-surface-border/50 pb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-ink-2 uppercase">Step {index + 1} of {events.length}</span>
                      <span>•</span>
                      <span>Event #{event.id}</span>
                      <span>•</span>
                      <span className="font-mono text-ink-2">{event.event_type}</span>
                      <span>•</span>
                      <span>Run #{event.run_id}</span>
                      <span>•</span>
                      <span>{event.created_at} UTC</span>
                    </div>

                    <div className="flex items-center gap-1.5 ml-auto">
                      <button
                        type="button"
                        onClick={(e) => toggleRawMode(event.id, e)}
                        className="rounded border border-surface-border bg-surface-2 px-2 py-0.5 text-[10px] text-ink-2 hover:bg-surface-3 hover:text-ink-1 transition"
                      >
                        {isRawMode ? "Visual View" : "Raw JSON"}
                      </button>

                      <button
                        type="button"
                        onClick={(e) => copyEventJson(event, e)}
                        className="flex items-center gap-1 rounded border border-surface-border bg-surface-2 px-2 py-0.5 text-[10px] text-ink-2 hover:bg-surface-3 hover:text-ink-1 transition"
                        title="Copy event payload as JSON"
                      >
                        {copiedId === event.id ? (
                          <>
                            <IconCheck className="h-3 w-3 text-status-success" />
                            <span className="text-status-success">Copied</span>
                          </>
                        ) : (
                          <>
                            <IconCopy className="h-3 w-3" />
                            <span>Copy</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Body Content */}
                  {hasData && parsedData ? (
                    isRawMode ? (
                      <pre className="rounded border border-surface-border bg-surface-1 p-2.5 text-[11px] font-mono text-ink-1 overflow-x-auto max-h-60 leading-relaxed">
                        {JSON.stringify(parsedData, null, 2)}
                      </pre>
                    ) : (
                      <div className="space-y-2">
                        {/* Specialized Sources List */}
                        {Array.isArray(parsedData.sources) && (
                          <div className="space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-ink-3">
                              Cross-Referenced Knowledge Sources ({parsedData.sources.length}):
                            </span>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-0.5">
                              {(parsedData.sources as string[]).map((src) => (
                                <div
                                  key={src}
                                  className="flex items-center gap-2 rounded border border-surface-border bg-surface-2/80 px-2 py-1 text-xs font-mono text-ink-1 shadow-2xs"
                                >
                                  <IconFileText className="h-3.5 w-3.5 text-status-knowledge shrink-0" />
                                  <span className="truncate">{src}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Key-Value Parameter Cards */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                          {Object.entries(parsedData)
                            .filter(([k]) => k !== "sources")
                            .map(([key, val]) => {
                              const label = formatLabel(key);
                              const isComplex = typeof val === "object" && val !== null;
                              const strVal = isComplex ? JSON.stringify(val) : String(val);

                              return (
                                <div
                                  key={key}
                                  className="rounded border border-surface-border/70 bg-surface-1 px-2.5 py-1.5 flex flex-col justify-between gap-1 shadow-2xs"
                                >
                                  <span className="text-[9px] font-bold uppercase tracking-wider text-ink-3 truncate">
                                    {label}
                                  </span>
                                  <div className="truncate">
                                    {typeof val === "boolean" ? (
                                      <StatusValueBadge value={val ? "TRUE" : "FALSE"} />
                                    ) : typeof val === "string" ? (
                                      <StatusValueBadge value={val} />
                                    ) : Array.isArray(val) ? (
                                      <div className="flex flex-wrap gap-1">
                                        {val.map((item, i) => (
                                          <span
                                            key={i}
                                            className="rounded bg-surface-3 px-1 py-0.2 text-[10px] font-mono text-ink-2 border border-surface-border"
                                          >
                                            {String(item)}
                                          </span>
                                        ))}
                                      </div>
                                    ) : (
                                      <span className="font-mono text-ink-1 text-xs font-semibold">
                                        {strVal}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )
                  ) : (
                    <div className="rounded border border-surface-border/50 bg-surface-1 p-2 text-ink-3 text-[11px] italic">
                      // Authoritative baseline logged with no external parameter payload.
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 4. Full Sovereign JSON Audit Trail Modal */}
      {showFullAuditModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4"
          onClick={() => setShowFullAuditModal(false)}
        >
          <div
            className="panel flex flex-col max-h-[85vh] w-full max-w-3xl overflow-hidden border border-surface-border shadow-2xl animate-in fade-in-50 zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-surface-border bg-surface-2 px-4 py-3">
              <div className="flex items-center gap-2">
                <IconTerminal className="h-4 w-4 text-brand" />
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-ink-1">
                  Sovereign Run Audit Trail — Run #{runId ?? (events[0]?.run_id || "Live")}
                </span>
                <span className="rounded bg-surface-3 px-1.5 py-0.5 text-[10px] font-mono text-ink-2 border border-surface-border">
                  {events.length} Milestones
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowFullAuditModal(false)}
                className="rounded p-1 text-ink-3 hover:bg-surface-3 hover:text-ink-1 transition"
                aria-label="Close modal"
              >
                <IconX className="h-4 w-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-4 bg-surface-0">
              <div className="mb-2 flex items-center justify-between text-[11px] text-ink-3">
                <span>Cryptographically unmodifiable SQLite audit event ledger.</span>
                <button
                  type="button"
                  onClick={copyAllAuditTrail}
                  className="flex items-center gap-1 rounded border border-brand/40 bg-brand/10 px-2.5 py-1 font-mono text-[11px] text-brand hover:bg-brand/20 transition"
                >
                  {copiedAll ? (
                    <>
                      <IconCheck className="h-3.5 w-3.5 text-status-success" />
                      <span className="text-status-success font-semibold">Audit Trail Copied!</span>
                    </>
                  ) : (
                    <>
                      <IconCopy className="h-3.5 w-3.5" />
                      <span>Copy Entire Audit JSON</span>
                    </>
                  )}
                </button>
              </div>

              <pre className="rounded border border-surface-border bg-surface-1 p-3 text-[11px] font-mono text-ink-1 overflow-x-auto leading-relaxed max-h-[55vh]">
                {JSON.stringify(
                  events.map((e) => ({
                    id: e.id,
                    run_id: e.run_id,
                    event_type: e.event_type,
                    message: e.message,
                    structured_data: parseData(e.structured_data),
                    created_at: e.created_at,
                  })),
                  null,
                  2
                )}
              </pre>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between border-t border-surface-border bg-surface-2 px-4 py-2.5 text-[11px] font-mono text-ink-3">
              <span>Local sovereign execution with no public-cloud AI/model dependency in the demonstrated workflow.</span>
              <button
                type="button"
                onClick={() => setShowFullAuditModal(false)}
                className="rounded border border-surface-border bg-surface-3 px-3 py-1 font-mono text-ink-1 hover:bg-surface-3/80 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}