import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "@/api/clients";
import { workspacesApi } from "@/api/workspaces";
import { Button } from "@/components/ui/Button";
import { IconLayers, IconPlus, IconX } from "@/components/ui/Icon";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/ui/States";
import { useWorkspaces } from "@/context/useWorkspaces";
import { formatDateTime } from "@/lib/format";
import type { Workspace } from "@/types";

function CreateWorkspaceForm({ onCreated, onCancel }: { onCreated: () => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [operatingMode, setOperatingMode] = useState("air_gapped");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await workspacesApi.create({
        name: name.trim(),
        description: description.trim() || null,
        operating_mode: operatingMode,
      });
      onCreated();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 403
            ? "Your role does not have permission to create workspaces."
            : err.message
          : "Failed to create workspace."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border-b border-surface-border bg-surface-1/40 p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="label mb-1 block" htmlFor="ws-name">
            Name
          </label>
          <input
            id="ws-name"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="MRPL-REFINERY-UNIT-01"
            autoFocus
          />
        </div>
        <div>
          <label className="label mb-1 block" htmlFor="ws-mode">
            Operating mode
          </label>
          <input
            id="ws-mode"
            className="input"
            value={operatingMode}
            onChange={(e) => setOperatingMode(e.target.value)}
            placeholder="air_gapped"
          />
        </div>
      </div>
      <div>
        <label className="label mb-1 block" htmlFor="ws-desc">
          Description
        </label>
        <textarea
          id="ws-desc"
          rows={2}
          className="textarea"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What this workspace scopes and who operates it."
        />
      </div>
      {error && <InlineError message={error} />}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" size="sm" loading={submitting} disabled={!name.trim()}>
          Create workspace
        </Button>
      </div>
    </form>
  );
}

export function WorkspacesPage() {
  const { workspaces, loading, error, refresh, selectedWorkspaceId, selectWorkspace } = useWorkspaces();
  const [showCreate, setShowCreate] = useState(false);
  const [detail, setDetail] = useState<Workspace | null>(null);

  useEffect(() => {
    if (!detail && workspaces.length > 0) {
      setDetail(workspaces.find((w) => w.id === selectedWorkspaceId) ?? workspaces[0]);
    }
  }, [workspaces, selectedWorkspaceId, detail]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Workspaces"
        description="Isolated operational scopes — each with its own agents, knowledge sources, and run history."
        actions={
          <Button variant="primary" size="sm" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? <IconX className="h-3.5 w-3.5" /> : <IconPlus className="h-3.5 w-3.5" />}
            {showCreate ? "Cancel" : "New workspace"}
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Panel className="lg:col-span-2">
          <PanelHeader icon={<IconLayers className="h-3.5 w-3.5" />} title="All Workspaces" meta={<span className="font-mono text-[10px] text-ink-3">{workspaces.length}</span>} />
          {showCreate && (
            <CreateWorkspaceForm
              onCreated={() => {
                setShowCreate(false);
                void refresh();
              }}
              onCancel={() => setShowCreate(false)}
            />
          )}
          <PanelBody className="p-0">
            {loading ? (
              <LoadingState />
            ) : error ? (
              <ErrorState message={error} />
            ) : workspaces.length === 0 ? (
              <EmptyState
                title="No workspaces yet"
                description="Create your first workspace to start operating."
              />
            ) : (
              <ul className="divide-y divide-surface-border">
                {workspaces.map((ws) => (
                  <li key={ws.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setDetail(ws);
                        selectWorkspace(ws.id);
                      }}
                      className={`flex w-full flex-col items-start gap-0.5 px-4 py-2.5 text-left transition-colors hover:bg-surface-3/60 ${
                        detail?.id === ws.id ? "bg-brand/5" : ""
                      }`}
                    >
                      <span className="text-sm font-medium text-ink-1">{ws.name}</span>
                      <span className="font-mono text-[10px] text-ink-3">{ws.operating_mode}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </PanelBody>
        </Panel>

        <Panel className="lg:col-span-3">
          <PanelHeader icon={<IconLayers className="h-3.5 w-3.5" />} title="Workspace Detail" />
          <PanelBody>
            {!detail ? (
              <EmptyState title="Select a workspace" description="Pick a workspace from the list to view its details." />
            ) : (
              <div className="space-y-4">
                <div>
                  <h2 className="text-base font-semibold text-ink-1">{detail.name}</h2>
                  {detail.description && <p className="mt-1 text-sm text-ink-3">{detail.description}</p>}
                </div>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 font-mono text-xs sm:grid-cols-3">
                  <div>
                    <dt className="text-ink-3">ID</dt>
                    <dd className="text-ink-1">#{detail.id}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">Operating mode</dt>
                    <dd className="text-ink-1">{detail.operating_mode}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">Created</dt>
                    <dd className="text-ink-1">{formatDateTime(detail.created_at)}</dd>
                  </div>
                </dl>
              </div>
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}