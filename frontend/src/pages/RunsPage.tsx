import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { artifactsApi } from "@/api/artifacts";
import { ApiError } from "@/api/clients";
import { runsApi } from "@/api/runs";
import { EventTimeline } from "@/components/EventTimeline";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconArchive, IconDownload, IconPlayCircle, IconRefresh } from "@/components/ui/Icon";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/ui/States";
import { useWorkspaces } from "@/context/useWorkspaces";
import { formatBytes, formatDateTime, formatRelativeTime, runStatusLabel, runStatusTone } from "@/lib/format";
import type { Artifact, Run, RunEvent } from "@/types";

function RunDetail({ run, onResumed }: { run: Run; onResumed: (r: Run) => void }) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [resuming, setResuming] = useState(false);
  const [resumeError, setResumeError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    artifactsApi
      .list(run.workspace_id)
      .then((res) => {
        if (!cancelled) {
          setArtifacts(res.artifacts.filter((a) => a.run_id === run.id));
        }
      })
      .catch(() => {
        if (!cancelled) setArtifacts([]);
      });
    return () => {
      cancelled = true;
    };
  }, [run.id, run.workspace_id]);

  useEffect(() => {
    let cancelled = false;
    setEventsLoading(true);
    runsApi
      .events(run.id)
      .then((list) => {
        if (!cancelled) setEvents(list);
      })
      .catch(() => {
        if (!cancelled) setEvents([]);
      })
      .finally(() => {
        if (!cancelled) setEventsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [run.id]);

  async function handleResume() {
    setResuming(true);
    setResumeError(null);
    try {
      const updated = await runsApi.resume(run.id);
      onResumed(updated);
    } catch (err) {
      setResumeError(
        err instanceof ApiError
          ? err.status === 403
            ? "Your role does not have permission to resume runs."
            : err.message
          : "Failed to resume run."
      );
    } finally {
      setResuming(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-ink-1">{run.input_text ?? "(no input text)"}</p>
          <p className="mt-1 font-mono text-[10px] text-ink-3">
            Run #{run.id} · Agent #{run.agent_id} · Started {formatDateTime(run.started_at)}
          </p>
        </div>
        <Badge tone={runStatusTone(run.status)}>{runStatusLabel(run.status)}</Badge>
      </div>

      {run.input_image_path && (
        <p className="font-mono text-[11px] text-status-knowledge">
          Attached image reference: {run.input_image_path}
        </p>
      )}

      {run.status === "paused" && (
        <div className="rounded border border-status-warning/30 bg-status-warning/5 p-3">
          <p className="text-xs text-status-warning">
            This run is paused pending a safety interlock approval. Resolve the request from the
            Approvals page, or resume directly if it has already been approved.
          </p>
          {resumeError && (
            <div className="mt-2">
              <InlineError message={resumeError} />
            </div>
          )}
          <Button variant="primary" size="sm" className="mt-2" onClick={handleResume} loading={resuming}>
            <IconRefresh className="h-3.5 w-3.5" /> Resume run
          </Button>
        </div>
      )}

      <div>
        <p className="label mb-1.5">Execution trace</p>
        <div className="max-h-64 overflow-y-auto rounded border border-surface-border bg-surface-1/50 p-3">
          {eventsLoading ? <LoadingState label="Loading trace…" /> : <EventTimeline events={events} />}
        </div>
      </div>

      {run.sources_used && (
        <div>
          <p className="label mb-1">Knowledge citations</p>
          <p className="rounded border border-surface-border bg-surface-1/50 p-2.5 font-mono text-xs text-status-knowledge/90">
            {run.sources_used}
          </p>
        </div>
      )}

      {run.result_text && (
        <div>
          <p className="label mb-1">Result</p>
          <div className="whitespace-pre-wrap rounded border border-surface-border bg-surface-1 p-3 text-sm leading-relaxed text-ink-1">
            {run.result_text}
          </div>
          {run.confidence !== null && run.confidence !== undefined && (
            <p className="mt-1 font-mono text-[10px] text-ink-3">Confidence: {(run.confidence * 100).toFixed(0)}%</p>
          )}
        </div>
      )}

      {artifacts.length > 0 && (
        <div className="space-y-2.5 rounded border border-surface-border bg-surface-2/60 p-3.5">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-mono font-bold uppercase tracking-wider text-ink-1">
              <IconArchive className="h-3.5 w-3.5 text-brand" />
              Generated Deliverables ({artifacts.length})
            </span>
            <span className="font-mono text-[10px] text-ink-3">CLICK TO DOWNLOAD</span>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {artifacts.map((art) => (
              <div
                key={art.id}
                className="flex items-center justify-between rounded border border-surface-border bg-surface-1 p-2.5 shadow-sm"
              >
                <div className="min-w-0 flex-1 pr-2">
                  <p className="truncate text-xs font-semibold text-ink-1" title={art.filename}>
                    {art.title || art.filename}
                  </p>
                  <p className="font-mono text-[10px] text-ink-3">
                    <span className="text-brand font-medium uppercase">{art.artifact_type}</span> · {formatBytes(art.file_size)}
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={async () => {
                    setDownloadingId(art.id);
                    try {
                      await artifactsApi.download(run.workspace_id, art.id, art.filename);
                    } finally {
                      setDownloadingId(null);
                    }
                  }}
                  loading={downloadingId === art.id}
                  title={`Download ${art.filename}`}
                >
                  <IconDownload className="h-3 w-3" /> Download
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {run.error_message && <InlineError message={run.error_message} />}
    </div>
  );
}

export function RunsPage() {
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspaces();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const selectedRunId = searchParams.get("run") ? Number(searchParams.get("run")) : null;
  const selectedRun = runs.find((r) => r.id === selectedRunId) ?? null;

  const load = async () => {
    if (!selectedWorkspaceId) {
      setRuns([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const list = await runsApi.list({ workspaceId: selectedWorkspaceId });
      const sorted = [...list].sort(
        (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
      );
      setRuns(sorted);
      if (!selectedRunId && sorted.length > 0) {
        setSearchParams({ run: String(sorted[0].id) }, { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWorkspaceId]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Runs"
        description={
          selectedWorkspace ? `Agent run history for ${selectedWorkspace.name}.` : "Agent run history."
        }
        actions={
          <Button variant="secondary" size="sm" onClick={() => void load()}>
            <IconRefresh className="h-3.5 w-3.5" /> Refresh
          </Button>
        }
      />

      {!selectedWorkspaceId ? (
        <EmptyState title="Select a workspace" description="Choose a workspace from the top bar to view its runs." />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <Panel className="lg:col-span-2">
            <PanelHeader
              icon={<IconPlayCircle className="h-3.5 w-3.5" />}
              title="Run History"
              meta={<span className="font-mono text-[10px] text-ink-3">{runs.length}</span>}
            />
            <PanelBody className="p-0">
              {loading ? (
                <LoadingState />
              ) : error ? (
                <ErrorState message={error} />
              ) : runs.length === 0 ? (
                <EmptyState title="No runs yet" description="Dispatch a query from the Operator console." />
              ) : (
                <ul className="max-h-[560px] divide-y divide-surface-border overflow-y-auto">
                  {runs.map((run) => (
                    <li key={run.id}>
                      <button
                        type="button"
                        onClick={() => setSearchParams({ run: String(run.id) })}
                        className={`flex w-full items-center justify-between gap-2 px-4 py-2.5 text-left transition-colors hover:bg-surface-3/60 ${
                          selectedRunId === run.id ? "bg-brand/5" : ""
                        }`}
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-xs text-ink-1">
                            {run.input_text ?? "(no input text)"}
                          </span>
                          <span className="block font-mono text-[10px] text-ink-3">
                            #{run.id} · {formatRelativeTime(run.started_at)}
                          </span>
                        </span>
                        <Badge tone={runStatusTone(run.status)}>{runStatusLabel(run.status)}</Badge>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </PanelBody>
          </Panel>

          <Panel className="lg:col-span-3">
            <PanelHeader icon={<IconPlayCircle className="h-3.5 w-3.5" />} title="Run Detail" />
            <PanelBody>
              {!selectedRun ? (
                <EmptyState title="Select a run" description="Pick a run from the list to inspect its trace." />
              ) : (
                <RunDetail
                  run={selectedRun}
                  onResumed={(updated) => setRuns((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))}
                />
              )}
            </PanelBody>
          </Panel>
        </div>
      )}
    </div>
  );
}