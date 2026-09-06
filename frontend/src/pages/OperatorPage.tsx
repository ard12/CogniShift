import { useCallback, useEffect, useRef, useState } from "react";
import { agentsApi } from "@/api/agents";
import { approvalsApi } from "@/api/approvals";
import { ApiError } from "@/api/clients";
import { knowledgeApi } from "@/api/knowledge";
import { runsApi } from "@/api/runs";
import { ApprovalCard } from "@/components/ApprovalCard";
import { EventTimeline } from "@/components/EventTimeline";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconAlertTriangle, IconImage, IconPlay, IconX } from "@/components/ui/Icon";
import { PageHeader } from "@/components/PageHeader";
import { Select } from "@/components/ui/Select";
import { EmptyState, InlineError } from "@/components/ui/States";
import { useWorkspaces } from "@/context/useWorkspaces";
import { runStatusLabel, runStatusTone } from "@/lib/format";
import type { Agent, Approval, Run, RunEvent } from "@/types";

const QUICK_SCENARIOS = [
  {
    label: "check-pt101-telemetry",
    tone: "neutral" as const,
    prompt:
      "What is the normal operating pressure for sensor PT-101 according to our SOP? Please check current pressure telemetry.",
  },
  {
    label: "trip-495psi-emergency",
    tone: "danger" as const,
    prompt:
      "Pressure transmitter PT-101 is reading 495 PSI! This exceeds 450 PSI! Actuate emergency pressure relief on chamber Reactor-B!",
  },
  {
    label: "verify-tt204-temp",
    tone: "neutral" as const,
    prompt:
      "Please check temperature telemetry on thermocouple TT-204 and verify against API 610 trip thresholds.",
  },
];

type RunLifecycle = "idle" | "dispatching" | "settled";

export function OperatorPage() {
  const { selectedWorkspaceId, selectedWorkspace, workspaces, loading: workspacesLoading } =
    useWorkspaces();

  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);

  const [prompt, setPrompt] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [lifecycle, setLifecycle] = useState<RunLifecycle>("idle");
  const [dispatchStage, setDispatchStage] = useState<string | null>(null);
  const [dispatchError, setDispatchError] = useState<string | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [relatedApproval, setRelatedApproval] = useState<Approval | null>(null);

  // Load agents whenever the active workspace changes.
  useEffect(() => {
    if (!selectedWorkspaceId) {
      setAgents([]);
      return;
    }
    let cancelled = false;
    setAgentsLoading(true);
    agentsApi
      .list(selectedWorkspaceId)
      .then((list) => {
        if (cancelled) return;
        setAgents(list);
        setSelectedAgentId((current) => {
          if (current && list.some((a) => a.id === current)) return current;
          return list[0]?.id ?? null;
        });
      })
      .catch(() => {
        if (!cancelled) setAgents([]);
      })
      .finally(() => {
        if (!cancelled) setAgentsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedWorkspaceId]);

  const applyScenario = (text: string) => setPrompt(text);

  const clearImage = () => {
    setImageFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const checkForApproval = useCallback(async (runId: number) => {
    try {
      const pending = await approvalsApi.listPending();
      setRelatedApproval(pending.find((a) => a.run_id === runId) ?? null);
    } catch {
      setRelatedApproval(null);
    }
  }, []);

  async function dispatch() {
    if (!selectedWorkspaceId || !selectedAgentId || !prompt.trim()) return;

    setLifecycle("dispatching");
    setDispatchError(null);
    setRun(null);
    setEvents([]);
    setRelatedApproval(null);

    try {
      let inputImagePath: string | null = null;
      if (imageFile) {
        setDispatchStage("Ingesting attached image through the knowledge pipeline…");
        const source = await knowledgeApi.upload(imageFile, selectedWorkspaceId);
        inputImagePath = source.local_path ?? null;
      }

      setDispatchStage("Dispatching to agent runtime…");
      const created = await runsApi.create({
        workspace_id: selectedWorkspaceId,
        agent_id: selectedAgentId,
        input_text: prompt.trim(),
        input_image_path: inputImagePath,
      });

      setRun(created);

      setDispatchStage("Fetching execution trace…");
      const eventList = await runsApi.events(created.id);
      setEvents(eventList);

      if (created.status === "paused") {
        await checkForApproval(created.id);
      }
    } catch (err) {
      setDispatchError(err instanceof ApiError ? err.message : "Dispatch failed unexpectedly.");
    } finally {
      setDispatchStage(null);
      setLifecycle("settled");
    }
  }

  async function refreshAfterApprovalResolved() {
    if (!run) return;
    try {
      const updated = await runsApi.get(run.id);
      setRun(updated);
      const eventList = await runsApi.events(run.id);
      setEvents(eventList);
      setRelatedApproval(null);
    } catch {
      // Leave prior state visible; the operator can retry manually.
    }
  }

  const canDispatch =
    lifecycle !== "dispatching" && !!selectedWorkspaceId && !!selectedAgentId && prompt.trim().length > 0;

  const runBadgeTone = run ? runStatusTone(run.status) : "neutral";
  const runBadgeLabel = lifecycle === "dispatching" ? "DISPATCHING" : run ? runStatusLabel(run.status).toUpperCase() : "IDLE";

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Operator Command Console"
        description="Dispatch operational queries and safety interventions to a CogniShift agent and observe the sovereign reasoning trace."
      />

      {!workspacesLoading && workspaces.length === 0 ? (
        <EmptyState
          title="No workspace access"
          description="Your account is not scoped to any workspace yet. Ask an administrator to grant access or create one from the Workspaces page."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
          {/* Left: command deck + terminal */}
          <div className="flex flex-col gap-4 xl:col-span-7">
            <div className="panel flex flex-col overflow-hidden">
              <div className="flex h-10 items-center justify-between border-b border-surface-border bg-surface-3/40 px-4">
                <span className="flex items-center gap-2 text-xs font-mono font-semibold uppercase tracking-wider text-ink-1">
                  Command Deck
                </span>
                <div className="flex items-center gap-2 text-[11px] text-ink-3">
                  <span className="hidden sm:inline">AGENT:</span>
                  <Select
                    className="w-56"
                    value={selectedAgentId ?? ""}
                    disabled={agentsLoading || agents.length === 0}
                    onChange={(e) => setSelectedAgentId(Number(e.target.value))}
                    aria-label="Select agent"
                  >
                    {agentsLoading && <option>Loading…</option>}
                    {!agentsLoading && agents.length === 0 && <option>No agents in workspace</option>}
                    {agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 border-b border-surface-border/60 bg-surface-1/40 px-4 py-2 text-[11px] font-mono">
                <span className="text-ink-3">quick:</span>
                {QUICK_SCENARIOS.map((scenario) => (
                  <button
                    key={scenario.label}
                    type="button"
                    onClick={() => applyScenario(scenario.prompt)}
                    className={
                      scenario.tone === "danger"
                        ? "rounded border border-status-error/40 bg-status-error/10 px-2 py-0.5 text-status-error transition hover:bg-status-error/20"
                        : "rounded border border-surface-border bg-surface-3/60 px-2 py-0.5 text-ink-2 transition hover:bg-surface-3"
                    }
                  >
                    $ {scenario.label}
                  </button>
                ))}
              </div>

              <div className="flex flex-col gap-3 p-4">
                <div className="flex items-start gap-2.5">
                  <span className="pt-2.5 font-mono text-sm font-bold text-brand select-none">
                    operator~$
                  </span>
                  <textarea
                    rows={3}
                    className="textarea flex-1 font-mono"
                    placeholder="Enter operational command, telemetry query, or safety intervention…"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.ctrlKey && e.key === "Enter") {
                        e.preventDefault();
                        if (canDispatch) void dispatch();
                      }
                    }}
                  />
                </div>

                {imageFile && (
                  <div className="flex items-center gap-2 rounded border border-surface-border bg-surface-3/50 px-2.5 py-1.5 text-xs text-ink-2">
                    <IconImage className="h-3.5 w-3.5 shrink-0 text-status-knowledge" />
                    <span className="truncate">{imageFile.name}</span>
                    <button
                      type="button"
                      onClick={clearImage}
                      className="ml-auto shrink-0 text-ink-3 hover:text-ink-1"
                      aria-label="Remove attached image"
                    >
                      <IconX className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}

                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                  <div className="flex items-center gap-3 text-xs text-ink-3">
                    <span className="hidden sm:inline">
                      <span className="kbd">Ctrl</span> + <span className="kbd">Enter</span> to execute
                    </span>
                    <Badge tone={runBadgeTone} pulse={lifecycle === "dispatching"}>
                      {runBadgeLabel}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/png,image/jpeg"
                      className="hidden"
                      onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => fileInputRef.current?.click()}
                      title="Attach an inspection photo (gauge dial, nameplate, etc.)"
                    >
                      <IconImage className="h-3.5 w-3.5" /> Attach image
                    </Button>
                    <Button
                      variant="primary"
                      onClick={() => void dispatch()}
                      disabled={!canDispatch}
                      loading={lifecycle === "dispatching"}
                    >
                      <IconPlay className="h-3.5 w-3.5" /> Execute
                    </Button>
                  </div>
                </div>

                {imageFile && (
                  <p className="text-[11px] leading-relaxed text-ink-3">
                    The attached image is first ingested through the Knowledge Vault to obtain a
                    server-side path, then referenced as visual input for this run.
                  </p>
                )}

                {dispatchError && <InlineError message={dispatchError} />}
              </div>
            </div>

            {/* Execution timeline */}
            <div className="panel flex flex-1 flex-col overflow-hidden">
              <div className="flex h-10 shrink-0 items-center justify-between border-b border-surface-border bg-surface-3/40 px-4">
                <span className="text-xs font-mono font-semibold uppercase tracking-wider text-ink-1">
                  Execution Trace
                </span>
                {run && <span className="font-mono text-[10px] text-ink-3">RUN #{run.id}</span>}
              </div>
              <div className="max-h-[420px] overflow-y-auto bg-surface-1/40 p-4">
                {dispatchStage && (
                  <p className="mb-2 font-mono text-[11px] text-status-info">{dispatchStage}</p>
                )}
                <EventTimeline events={events} />
              </div>

              {run?.sources_used && (
                <div className="border-t border-surface-border bg-surface-1/60 px-4 py-2.5 font-mono text-xs">
                  <span className="font-semibold text-ink-2">VERIFIED KNOWLEDGE CITATIONS:</span>
                  <p className="mt-0.5 truncate text-status-knowledge/90">{run.sources_used}</p>
                </div>
              )}

              {run?.result_text && (
                <div className="space-y-2 border-t border-surface-border bg-surface-2 p-4">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-xs font-mono font-bold uppercase tracking-wider text-ink-1">
                      Operational Synthesis
                    </span>
                    {run.model_name && (
                      <span className="font-mono text-[10px] text-ink-3">
                        GENERATED LOCALLY ({run.model_name.toUpperCase()})
                      </span>
                    )}
                  </div>
                  <div className="whitespace-pre-wrap rounded border border-surface-border bg-surface-1 p-3 text-sm leading-relaxed text-ink-1">
                    {run.result_text}
                  </div>
                  {run.confidence !== null && run.confidence !== undefined && (
                    <p className="font-mono text-[10px] text-ink-3">
                      Confidence: {(run.confidence * 100).toFixed(0)}%
                    </p>
                  )}
                </div>
              )}

              {run?.error_message && (
                <div className="border-t border-surface-border p-4">
                  <InlineError message={run.error_message} />
                </div>
              )}
            </div>
          </div>

          {/* Right: approval gate + knowledge context */}
          <div className="flex flex-col gap-4 xl:col-span-5">
            <div className="panel flex flex-col gap-3 p-4">
              <div className="flex items-center justify-between border-b border-surface-border pb-2.5">
                <span className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-ink-1">
                  Shift Supervisor Authorization
                </span>
                <Badge tone={relatedApproval ? "warning" : "neutral"}>
                  {relatedApproval ? "1 PENDING" : "0 PENDING"}
                </Badge>
              </div>

              {run?.status === "paused" && relatedApproval ? (
                <ApprovalCard approval={relatedApproval} onResolved={refreshAfterApprovalResolved} />
              ) : run?.status === "paused" ? (
                <div className="flex items-center gap-2 rounded border border-status-warning/30 bg-status-warning/5 px-3 py-4 text-xs text-status-warning">
                  <IconAlertTriangle className="h-4 w-4 shrink-0" />
                  This run is paused pending approval, but the request could not be found in your
                  queue — you may not hold the reviewer role for this workspace.
                </div>
              ) : (
                <p className="py-6 text-center font-mono text-xs italic text-ink-3">
                  All safety interlocks nominal.
                  <br />
                  <span className="text-[10px] text-ink-3/70">
                    Zero high-risk interventions gated for this session.
                  </span>
                </p>
              )}
            </div>

            <div className="panel flex flex-col gap-2 p-4 text-xs text-ink-3">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-ink-1">
                Session Context
              </span>
              <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1.5 font-mono text-[11px]">
                <dt className="text-ink-3">Workspace</dt>
                <dd className="text-ink-1">{selectedWorkspace?.name ?? "—"}</dd>
                <dt className="text-ink-3">Mode</dt>
                <dd className="text-ink-1">{selectedWorkspace?.operating_mode ?? "—"}</dd>
                <dt className="text-ink-3">Model</dt>
                <dd className="text-ink-1">{run?.model_name ?? "—"}</dd>
              </dl>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}