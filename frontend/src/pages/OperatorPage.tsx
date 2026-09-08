import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { agentsApi } from "@/api/agents";
import { approvalsApi } from "@/api/approvals";
import { artifactsApi } from "@/api/artifacts";
import { ApiError } from "@/api/clients";
import { knowledgeApi } from "@/api/knowledge";
import { runsApi } from "@/api/runs";
import { ApprovalCard } from "@/components/ApprovalCard";
import { EventTimeline } from "@/components/EventTimeline";
import { RequestFlow } from "@/components/RequestFlow";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  IconAlertTriangle,
  IconArchive,
  IconBook,
  IconDownload,
  IconImage,
  IconPlay,
  IconPlus,
  IconX,
} from "@/components/ui/Icon";
import { PageHeader } from "@/components/PageHeader";
import { Select } from "@/components/ui/Select";
import { EmptyState, InlineError } from "@/components/ui/States";
import { useWorkspaces } from "@/context/useWorkspaces";
import { formatBytes, runStatusLabel, runStatusTone } from "@/lib/format";
import type { Agent, Approval, Artifact, Run, RunEvent, RunStatusSummary } from "@/types";

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
  const navigate = useNavigate();
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
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [artifactImages, setArtifactImages] = useState<Record<number, string>>({});
  const [statusSummary, setStatusSummary] = useState<RunStatusSummary | null>(null);

  useEffect(() => {
    if (!run) { setStatusSummary(null); return; }
    let cancelled = false;
    runsApi.statusSummary(run.id).then((summary) => { if (!cancelled) setStatusSummary(summary); }).catch(() => { if (!cancelled) setStatusSummary(null); });
    return () => { cancelled = true; };
  }, [run, events.length]);

  // Rehydrate draft prompt on workspace change
  useEffect(() => {
    if (!selectedWorkspaceId) return;
    const saved = sessionStorage.getItem(`cognishift_operator_prompt_${selectedWorkspaceId}`);
    if (saved !== null) {
      setPrompt(saved);
    }
  }, [selectedWorkspaceId]);

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
        const savedAgentId = sessionStorage.getItem(`cognishift_operator_agent_${selectedWorkspaceId}`);
        const parsedSavedAgent = savedAgentId ? Number(savedAgentId) : null;
        setSelectedAgentId((current) => {
          if (parsedSavedAgent && list.some((a) => a.id === parsedSavedAgent)) return parsedSavedAgent;
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

  const applyScenario = (text: string) => {
    setPrompt(text);
    if (selectedWorkspaceId) {
      sessionStorage.setItem(`cognishift_operator_prompt_${selectedWorkspaceId}`, text);
    }
  };

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

  // Rehydrate active run on mount / workspace switch
  useEffect(() => {
    if (!selectedWorkspaceId) {
      setRun(null);
      setEvents([]);
      return;
    }
    let cancelled = false;
    const savedRunId = sessionStorage.getItem(`cognishift_operator_run_id_${selectedWorkspaceId}`);

    async function loadInitialRun() {
      try {
        if (savedRunId) {
          const runIdNum = Number(savedRunId);
          const [loadedRun, loadedEvents] = await Promise.all([
            runsApi.get(runIdNum),
            runsApi.events(runIdNum),
          ]);
          if (!cancelled) {
            setRun(loadedRun);
            setEvents(loadedEvents);
            if (loadedRun.status === "paused") {
              void checkForApproval(loadedRun.id);
            }
          }
        } else {
          const list = await runsApi.list({ workspaceId: selectedWorkspaceId ?? undefined });
          if (!cancelled && list.length > 0) {
            const latest = list[0];
            const loadedEvents = await runsApi.events(latest.id);
            if (!cancelled) {
              setRun(latest);
              setEvents(loadedEvents);
              if (latest.status === "paused") {
                void checkForApproval(latest.id);
              }
            }
          }
        }
      } catch {
        // Fallback gracefully
      }
    }

    void loadInitialRun();
    return () => {
      cancelled = true;
    };
  }, [selectedWorkspaceId, checkForApproval]);

  // Live auto-sync polling for paused runs
  useEffect(() => {
    if (!run || run.status !== "paused") return;
    const interval = setInterval(async () => {
      try {
        const updated = await runsApi.get(run.id);
        if (updated.status !== "paused") {
          setRun(updated);
          const evts = await runsApi.events(run.id);
          setEvents(evts);
          setRelatedApproval(null);
        }
      } catch {
        // Continue polling
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [run]);

  // Load deliverables/artifacts for active run
  useEffect(() => {
    if (!selectedWorkspaceId || !run) {
      setArtifacts([]);
      return;
    }
    let cancelled = false;
    artifactsApi.list(selectedWorkspaceId)
      .then(async (res) => {
        if (cancelled) return;
        const runArts = res.artifacts.filter((a) => a.run_id === run.id);
        setArtifacts(runArts);

        for (const art of runArts) {
          const typeLower = art.artifact_type.toLowerCase();
          if (["png", "jpg", "jpeg"].includes(typeLower) && !artifactImages[art.id]) {
            try {
              const blobUrl = await artifactsApi.getBlobUrl(selectedWorkspaceId, art.id);
              if (!cancelled) {
                setArtifactImages((prev) => ({ ...prev, [art.id]: blobUrl }));
              }
            } catch {
              // Ignore blob load error
            }
          }
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
    // Fetching image blobs updates artifactImages; rerunning for that state would refetch every artifact.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWorkspaceId, run]);

  const handleClearSession = () => {
    setPrompt("");
    setRun(null);
    setEvents([]);
    setArtifacts([]);
    setRelatedApproval(null);
    setDispatchError(null);
    clearImage();
    if (selectedWorkspaceId) {
      sessionStorage.removeItem(`cognishift_operator_prompt_${selectedWorkspaceId}`);
      sessionStorage.removeItem(`cognishift_operator_run_id_${selectedWorkspaceId}`);
    }
  };

  async function dispatch() {
    if (!selectedWorkspaceId || !selectedAgentId || !prompt.trim()) return;

    setLifecycle("dispatching");
    setDispatchError(null);
    const priorRun = run;
    setRun(null);
    setEvents([]);
    setArtifacts([]);
    setRelatedApproval(null);

    try {
      let inputImagePath: string | null = null;
      if (imageFile) {
        setDispatchStage("Ingesting attached file through the knowledge pipeline…");
        const source = await knowledgeApi.upload(imageFile, selectedWorkspaceId);
        const isImage = imageFile.type.startsWith("image/") || /\.(png|jpe?g)$/i.test(imageFile.name);
        if (isImage) {
          inputImagePath = source.local_path ?? null;
        }
      }

      // Auto-clear image attachment immediately so subsequent prompts do not re-upload it
      clearImage();

      setDispatchStage("Dispatching to agent runtime…");
      const history: Array<{ role: string; content: string }> = [];
      if (priorRun && priorRun.input_text && priorRun.result_text) {
        history.push({ role: "user", content: priorRun.input_text });
        history.push({ role: "assistant", content: priorRun.result_text });
      }

      const created = await runsApi.create({
        workspace_id: selectedWorkspaceId,
        agent_id: selectedAgentId,
        input_text: prompt.trim(),
        input_image_path: inputImagePath,
        conversation_history: history,
      });

      // Persist active runId in sessionStorage
      sessionStorage.setItem(`cognishift_operator_run_id_${selectedWorkspaceId}`, String(created.id));

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
                <div className="flex items-center gap-3">
                  {(prompt.trim().length > 0 || run !== null) && (
                    <button
                      type="button"
                      onClick={handleClearSession}
                      className="flex items-center gap-1 rounded border border-surface-border bg-surface-2 px-2 py-0.5 text-[11px] font-mono text-ink-2 transition hover:bg-surface-3 hover:text-ink-1"
                      title="Clear draft prompt and active run to start a new command"
                    >
                      <IconPlus className="h-3 w-3" /> New Command
                    </button>
                  )}
                  <div className="flex items-center gap-2 text-[11px] text-ink-3">
                    <span className="hidden sm:inline">AGENT:</span>
                    <Select
                      className="w-56"
                      value={selectedAgentId ?? ""}
                      disabled={agentsLoading || agents.length === 0}
                      onChange={(e) => {
                        const newId = Number(e.target.value);
                        setSelectedAgentId(newId);
                        if (selectedWorkspaceId) {
                          sessionStorage.setItem(`cognishift_operator_agent_${selectedWorkspaceId}`, String(newId));
                        }
                      }}
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
                    onChange={(e) => {
                      setPrompt(e.target.value);
                      if (selectedWorkspaceId) {
                        sessionStorage.setItem(`cognishift_operator_prompt_${selectedWorkspaceId}`, e.target.value);
                      }
                    }}
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
                      accept=".xlsx,.csv,.pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => fileInputRef.current?.click()}
                      title="Attach file (Excel spreadsheet, PDF manual, CSV, or inspection photo)"
                    >
                      <IconImage className="h-3.5 w-3.5" /> Attach file / image
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
                    The attached file ({imageFile.name}) is ingested through the Knowledge Vault into the workspace for immediate agent retrieval and analysis.
                  </p>
                )}

                {dispatchError && <InlineError message={dispatchError} />}
              </div>
            </div>

            <RequestFlow summary={statusSummary} />

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
                  <span className="font-semibold text-ink-2">DATA SOURCES USED:</span>
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
                        {run.operating_mode?.toLowerCase() === "local" ? "GENERATED LOCALLY" : "EXECUTION LOCATION UNAVAILABLE"} ({run.model_name.toUpperCase()})
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

                  {/* Interactive UI Navigation Action */}
                  {(() => {
                    const routingInfo = run.routing_info;
                    const details = routingInfo?.details;
                    const nestedTarget = details && typeof details === "object" && "target_route" in details
                      ? (details as { target_route?: unknown }).target_route
                      : undefined;
                    const directTarget = routingInfo?.target_route;
                    const targetRoute = (typeof directTarget === "string" ? directTarget : undefined)
                      || (typeof nestedTarget === "string" ? nestedTarget : undefined)
                      || (run.result_text?.includes("/knowledge") ? "/knowledge"
                      : run.result_text?.includes("/approvals") ? "/approvals"
                      : run.result_text?.includes("/agents") ? "/agents"
                      : run.result_text?.includes("/workspaces") ? "/workspaces"
                      : run.result_text?.includes("/system") ? "/system"
                      : run.result_text?.includes("/dashboard") ? "/dashboard"
                      : null);

                    const isNav = routingInfo?.intent === "UI_NAVIGATION" 
                      || run.result_text?.includes("Navigating to") 
                      || run.result_text?.includes("access **") 
                      || run.result_text?.includes("Knowledge Vault");

                    if (!targetRoute || !isNav) return null;

                    const nestedFriendly = details && typeof details === "object" && "friendly_name" in details
                      ? (details as { friendly_name?: unknown }).friendly_name
                      : undefined;
                    const friendlyName = (typeof nestedFriendly === "string" ? nestedFriendly : undefined)
                      || (targetRoute === "/knowledge" ? "Knowledge Vault"
                      : targetRoute === "/approvals" ? "Approvals"
                      : targetRoute === "/agents" ? "Agents"
                      : targetRoute === "/system" ? "System"
                      : "Portal");

                    return (
                      <div className="flex items-center justify-between rounded border border-brand/40 bg-brand/10 p-3 mt-3">
                        <div className="flex items-center gap-2">
                          <IconBook className="h-4 w-4 text-brand" />
                          <div>
                            <span className="block text-xs font-mono font-bold uppercase tracking-wide text-brand">
                              Direct Interface Navigation
                            </span>
                            <span className="text-[11px] text-ink-2">
                              Destination: <strong className="text-ink-1">{friendlyName}</strong> ({targetRoute})
                            </span>
                          </div>
                        </div>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => navigate(targetRoute)}
                        >
                          Open {friendlyName} →
                        </Button>
                      </div>
                    );
                  })()}
                </div>
              )}

              {artifacts.length > 0 && (
                <div className="space-y-3 border-t border-surface-border bg-surface-2/70 p-4">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-xs font-mono font-bold uppercase tracking-wider text-ink-1">
                      <IconArchive className="h-4 w-4 text-brand" />
                      Generated Artifacts & Visualizations ({artifacts.length})
                    </span>
                    <span className="font-mono text-[10px] text-ink-3">
                      ISOLATED SANDBOX ARTIFACTS
                    </span>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {artifacts.map((art) => {
                      const typeLower = art.artifact_type.toLowerCase();
                      const isImage = ["png", "jpg", "jpeg"].includes(typeLower);
                      const imageUrl = artifactImages[art.id];

                      return (
                        <div
                          key={art.id}
                          className="flex flex-col rounded-lg border border-surface-border bg-surface-1 overflow-hidden shadow-sm"
                        >
                          {isImage && imageUrl && (
                            <div className="relative border-b border-surface-border bg-black/20 p-2 flex items-center justify-center max-h-48 overflow-hidden">
                              <img
                                src={imageUrl}
                                alt={art.title || art.filename}
                                className="max-h-44 object-contain rounded transition hover:scale-105 cursor-pointer"
                                onClick={() => window.open(imageUrl, "_blank")}
                                title="Click to view full size"
                              />
                            </div>
                          )}

                          <div className="flex flex-1 flex-col justify-between p-3 gap-2">
                            <div>
                              <div className="flex items-center gap-2">
                                <Badge tone="info" className="uppercase font-mono text-[10px]">
                                  {art.artifact_type}
                                </Badge>
                                <span className="truncate font-mono text-xs font-semibold text-ink-1" title={art.filename}>
                                  {art.filename}
                                </span>
                              </div>
                              {art.description && (
                                <p className="mt-1 line-clamp-2 text-[11px] text-ink-3">
                                  {art.description}
                                </p>
                              )}
                            </div>

                            <div className="flex items-center justify-between pt-2 border-t border-surface-border/50 text-[11px] text-ink-3 font-mono">
                              <span>{formatBytes(art.file_size)}</span>
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() =>
                                  selectedWorkspaceId &&
                                  void artifactsApi.download(selectedWorkspaceId, art.id, art.filename)
                                }
                                title={`Download ${art.filename}`}
                              >
                                <IconDownload className="h-3 w-3" /> Download
                              </Button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
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
                  <dd className="text-ink-1">{run?.model_name ? `${run.model_name}${run.input_type === "multimodal" ? " (orchestrator)" : ""}` : "—"}</dd>
              </dl>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
