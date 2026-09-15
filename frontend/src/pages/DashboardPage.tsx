import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { approvalsApi } from "@/api/approvals";
import { knowledgeApi } from "@/api/knowledge";
import { runsApi } from "@/api/runs";
import { systemApi } from "@/api/system";
import { Badge } from "@/components/ui/Badge";
import {
  IconArchive,
  IconBook,
  IconCpu,
  IconLayers,
  IconPlayCircle,
  IconShieldCheck,
} from "@/components/ui/Icon";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { useAuth } from "@/auth/useAuth";
import { useWorkspaces } from "@/context/useWorkspaces";
import { formatRelativeTime, processingStatusTone, runStatusLabel, runStatusTone } from "@/lib/format";
import type { Approval, KnowledgeSource, Run, SystemStatus } from "@/types";

function useAsync<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    loader()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error };
}

export function DashboardPage() {
  const { sovereignty, role } = useAuth();
  const canReview = role === "supervisor" || role === "administrator";
  const isAdmin = role === "administrator";
  const { workspaces, selectedWorkspaceId, selectedWorkspace, loading: workspacesLoading } =
    useWorkspaces();

  const { data: systemStatus, loading: systemLoading, error: systemError } = useAsync<SystemStatus>(
    () => systemApi.status(),
    []
  );

  const { data: runs, loading: runsLoading } = useAsync<Run[]>(
    () => (selectedWorkspaceId ? runsApi.list({ workspaceId: selectedWorkspaceId }) : Promise.resolve([])),
    [selectedWorkspaceId]
  );

  const { data: approvals, loading: approvalsLoading } = useAsync<Approval[]>(
    () => (canReview ? approvalsApi.listPending() : Promise.resolve([])),
    [canReview]
  );

  const { data: knowledge, loading: knowledgeLoading } = useAsync<KnowledgeSource[]>(
    () => (canReview && selectedWorkspaceId ? knowledgeApi.list(selectedWorkspaceId) : Promise.resolve([])),
    [canReview, selectedWorkspaceId]
  );

  const recentRuns = [...(runs ?? [])]
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    .slice(0, 5);

  const processingCounts = (knowledge ?? []).reduce<Record<string, number>>((acc, k) => {
    acc[k.processing_status] = (acc[k.processing_status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Operator Overview"
        description="A consolidated snapshot of system health, sovereignty enforcement, and outstanding operational work."
      />

      {/* Top status strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          icon={<IconCpu className="h-4 w-4" />}
          label="Operating Mode"
          value={systemStatus?.operating_mode ?? (systemLoading ? "…" : "Unknown")}
        />
        <StatCard
          icon={<IconLayers className="h-4 w-4" />}
          label="Workspaces"
          value={workspacesLoading ? "…" : String(workspaces.length)}
        />
        {canReview && <StatCard
          icon={<IconShieldCheck className="h-4 w-4" />}
          label="Pending Approvals"
          value={approvalsLoading ? "…" : String(approvals?.length ?? 0)}
          tone={approvals && approvals.length > 0 ? "warning" : "success"}
        />}
        {canReview && <StatCard
          icon={<IconBook className="h-4 w-4" />}
          label="Knowledge Sources"
          value={knowledgeLoading ? "…" : String(knowledge?.length ?? 0)}
        />}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* System & sovereignty */}
        <Panel>
          <PanelHeader icon={<IconCpu className="h-3.5 w-3.5" />} title="System & Sovereignty" />
          <PanelBody className="space-y-3">
            {systemLoading ? (
              <LoadingState />
            ) : systemError ? (
              <ErrorState message={systemError} />
            ) : systemStatus ? (
              <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-2 font-mono text-xs">
                <dt className="text-ink-3">Version</dt>
                <dd className="text-ink-1">{systemStatus.version}</dd>
                <dt className="text-ink-3">Ollama</dt>
                <dd>
                  <Badge tone={systemStatus.ollama_available ? "success" : "danger"}>
                    {systemStatus.ollama_available ? "Available" : "Unavailable"}
                  </Badge>
                </dd>
                <dt className="text-ink-3">Database</dt>
                <dd>
                  <Badge tone={systemStatus.database_initialized ? "success" : "danger"}>
                    {systemStatus.database_initialized ? "Ready" : "Not initialized"}
                  </Badge>
                </dd>
                <dt className="text-ink-3">Local models</dt>
                <dd className="text-ink-1">{systemStatus.available_models.length}</dd>
                {sovereignty && (
                  <>
                    <dt className="text-ink-3">Sovereignty</dt>
                    <dd>
                      <Badge tone={sovereignty.sovereignty_enforced ? "success" : "warning"}>
                        {sovereignty.sovereignty_enforced ? "Enforced" : "Not enforced"}
                      </Badge>
                    </dd>
                    <dt className="text-ink-3">Blocked egress</dt>
                    <dd className="text-ink-1">{sovereignty.total_blocked_attempts}</dd>
                  </>
                )}
              </dl>
            ) : (
              <EmptyState title="No data" />
            )}
            <Link to={isAdmin ? "/system" : "/security"} className="inline-block text-[11px] font-mono text-brand hover:underline">
              {isAdmin ? "View full system status" : "View security status"} →
            </Link>
          </PanelBody>
        </Panel>

        {/* Workspace summary */}
        <Panel>
          <PanelHeader icon={<IconLayers className="h-3.5 w-3.5" />} title="Active Workspace" />
          <PanelBody className="space-y-2">
            {workspacesLoading ? (
              <LoadingState />
            ) : selectedWorkspace ? (
              <div className="space-y-2 font-mono text-xs">
                <p className="text-sm font-sans font-semibold text-ink-1">{selectedWorkspace.name}</p>
                {selectedWorkspace.description && (
                  <p className="font-sans text-xs text-ink-3">{selectedWorkspace.description}</p>
                )}
                <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1.5 pt-1">
                  <dt className="text-ink-3">Mode</dt>
                  <dd className="text-ink-1">{selectedWorkspace.operating_mode}</dd>
                  <dt className="text-ink-3">Created</dt>
                  <dd className="text-ink-1">{formatRelativeTime(selectedWorkspace.created_at)}</dd>
                </dl>
              </div>
            ) : (
              <EmptyState
                title="No workspace selected"
                description="Create or select a workspace to begin operating."
              />
            )}
            {canReview && <Link to="/workspaces" className="inline-block text-[11px] font-mono text-brand hover:underline">
              Manage workspaces →
            </Link>}
          </PanelBody>
        </Panel>

        {/* Knowledge summary is restricted to roles that may access the vault. */}
        {canReview && <Panel>
          <PanelHeader icon={<IconBook className="h-3.5 w-3.5" />} title="Knowledge Vault" />
          <PanelBody className="space-y-2">
            {knowledgeLoading ? (
              <LoadingState />
            ) : (knowledge ?? []).length === 0 ? (
              <EmptyState title="No documents ingested" description="Upload manuals or images from the Knowledge page." />
            ) : (
              <div className="space-y-1.5 font-mono text-xs">
                {Object.entries(processingCounts).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <Badge tone={processingStatusTone(status)}>{status}</Badge>
                    <span className="text-ink-1">{count}</span>
                  </div>
                ))}
              </div>
            )}
            <Link to="/knowledge" className="inline-block text-[11px] font-mono text-brand hover:underline">
              Open knowledge vault →
            </Link>
          </PanelBody>
        </Panel>}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {/* Recent runs */}
        <Panel>
          <PanelHeader icon={<IconPlayCircle className="h-3.5 w-3.5" />} title="Recent Runs" />
          <PanelBody>
            {runsLoading ? (
              <LoadingState />
            ) : recentRuns.length === 0 ? (
              <EmptyState title="No runs yet" description="Dispatch a query from the Operator console." />
            ) : (
              <ul className="divide-y divide-surface-border">
                {recentRuns.map((r) => (
                  <li key={r.id} className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <p className="truncate text-xs text-ink-1">{r.input_text ?? "(no input text)"}</p>
                      <p className="font-mono text-[10px] text-ink-3">
                        #{r.id} · {formatRelativeTime(r.started_at)}
                      </p>
                    </div>
                    <Badge tone={runStatusTone(r.status)}>{runStatusLabel(r.status)}</Badge>
                  </li>
                ))}
              </ul>
            )}
            <Link to="/runs" className="mt-2 inline-block text-[11px] font-mono text-brand hover:underline">
              View all runs →
            </Link>
          </PanelBody>
        </Panel>

        {/* Approval data is restricted to supervisors and administrators. */}
        {canReview && <Panel>
          <PanelHeader icon={<IconShieldCheck className="h-3.5 w-3.5" />} title="Pending Approvals" />
          <PanelBody>
            {approvalsLoading ? (
              <LoadingState />
            ) : (approvals ?? []).length === 0 ? (
              <EmptyState title="All safety interlocks nominal" description="Zero high-risk interventions gated." />
            ) : (
              <ul className="divide-y divide-surface-border">
                {(approvals ?? []).slice(0, 5).map((a) => (
                  <li key={a.id} className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <p className="truncate text-xs text-ink-1">{a.request_reason ?? "No reason provided"}</p>
                      <p className="font-mono text-[10px] text-ink-3">
                        Run #{a.run_id} · {formatRelativeTime(a.requested_at)}
                      </p>
                    </div>
                    <Badge tone="warning">{a.risk_level ?? "unknown"}</Badge>
                  </li>
                ))}
              </ul>
            )}
            <Link to="/approvals" className="mt-2 inline-block text-[11px] font-mono text-brand hover:underline">
              Review approvals →
            </Link>
          </PanelBody>
        </Panel>}
      </div>

      <Panel>
        <PanelHeader icon={<IconArchive className="h-3.5 w-3.5" />} title="Quick Links" />
        <PanelBody className="flex flex-wrap gap-2">
          <Link to="/operator" className="btn btn-secondary text-xs">
            Open Operator Console
          </Link>
          <Link to="/artifacts" className="btn btn-secondary text-xs">
            Browse Artifacts
          </Link>
          {isAdmin && <Link to="/agents" className="btn btn-secondary text-xs">
            Manage Agents
          </Link>}
        </PanelBody>
      </Panel>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  tone = "neutral",
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone?: "neutral" | "success" | "warning";
}) {
  const toneClass =
    tone === "warning" ? "text-status-warning" : tone === "success" ? "text-status-success" : "text-ink-1";
  return (
    <div className="panel flex items-center gap-3 p-3.5">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-surface-3 text-brand">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="truncate text-[10px] font-mono uppercase tracking-wide text-ink-3">{label}</p>
        <p className={`truncate text-sm font-semibold ${toneClass}`}>{value}</p>
      </div>
    </div>
  );
}
