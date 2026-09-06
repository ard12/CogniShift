import { useEffect, useState, type FormEvent } from "react";
import { agentsApi } from "@/api/agents";
import { ApiError } from "@/api/clients";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconBot, IconPlus, IconX } from "@/components/ui/Icon";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { EmptyState, ErrorState, InlineError, LoadingState } from "@/components/ui/States";
import { useWorkspaces } from "@/context/useWorkspaces";
import { formatDateTime } from "@/lib/format";
import type { Agent } from "@/types";

function parseIdList(value: string): number[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map(Number)
    .filter((n) => Number.isInteger(n) && n > 0);
}

function CreateAgentForm({
  workspaceId,
  onCreated,
  onCancel,
}: {
  workspaceId: number;
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemInstructions, setSystemInstructions] = useState("");
  const [modelName, setModelName] = useState("llama3.2:3b");
  const [approvalRequired, setApprovalRequired] = useState(true);
  const [toolIds, setToolIds] = useState("");
  const [knowledgeIds, setKnowledgeIds] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await agentsApi.create({
        workspace_id: workspaceId,
        name: name.trim(),
        description: description.trim() || null,
        system_instructions: systemInstructions.trim() || null,
        model_name: modelName.trim() || undefined,
        approval_required: approvalRequired,
        allowed_tool_ids: parseIdList(toolIds),
        knowledge_source_ids: parseIdList(knowledgeIds),
      });
      onCreated();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 403
            ? "Your role does not have permission to create agents."
            : err.message
          : "Failed to create agent."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border-b border-surface-border bg-surface-1/40 p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="label mb-1 block" htmlFor="ag-name">
            Name
          </label>
          <input id="ag-name" className="input" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <div>
          <label className="label mb-1 block" htmlFor="ag-model">
            Model
          </label>
          <input id="ag-model" className="input font-mono" value={modelName} onChange={(e) => setModelName(e.target.value)} />
        </div>
      </div>
      <div>
        <label className="label mb-1 block" htmlFor="ag-desc">
          Description
        </label>
        <input id="ag-desc" className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div>
        <label className="label mb-1 block" htmlFor="ag-sys">
          System instructions
        </label>
        <textarea
          id="ag-sys"
          rows={3}
          className="textarea"
          value={systemInstructions}
          onChange={(e) => setSystemInstructions(e.target.value)}
        />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="label mb-1 block" htmlFor="ag-tools">
            Allowed tool IDs (comma-separated)
          </label>
          <input id="ag-tools" className="input font-mono" value={toolIds} onChange={(e) => setToolIds(e.target.value)} placeholder="1, 2, 3" />
          <p className="mt-1 text-[10px] text-ink-3">
            The backend has no tool-listing endpoint — IDs come from the seeded tool registry.
          </p>
        </div>
        <div>
          <label className="label mb-1 block" htmlFor="ag-knowledge">
            Knowledge source IDs (comma-separated)
          </label>
          <input
            id="ag-knowledge"
            className="input font-mono"
            value={knowledgeIds}
            onChange={(e) => setKnowledgeIds(e.target.value)}
            placeholder="See IDs on the Knowledge page"
          />
        </div>
      </div>
      <label className="flex items-center gap-2 text-xs text-ink-2">
        <input
          type="checkbox"
          checked={approvalRequired}
          onChange={(e) => setApprovalRequired(e.target.checked)}
          className="h-3.5 w-3.5 rounded border-surface-border bg-surface-3"
        />
        Require human approval for high-risk tool calls
      </label>
      {error && <InlineError message={error} />}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" size="sm" loading={submitting} disabled={!name.trim()}>
          Create agent
        </Button>
      </div>
    </form>
  );
}

function AgentDetail({ agent, onUpdated }: { agent: Agent; onUpdated: (a: Agent) => void }) {
  const [status, setStatus] = useState(agent.status);
  const [approvalRequired, setApprovalRequired] = useState(agent.approval_required);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setStatus(agent.status);
    setApprovalRequired(agent.approval_required);
  }, [agent]);

  const dirty = status !== agent.status || approvalRequired !== agent.approval_required;

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const updated = await agentsApi.update(agent.id, { status, approval_required: approvalRequired });
      onUpdated(updated);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 403
            ? "Your role does not have permission to update agents."
            : err.message
          : "Failed to update agent."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-ink-1">{agent.name}</h2>
        {agent.description && <p className="mt-1 text-sm text-ink-3">{agent.description}</p>}
      </div>

      {agent.system_instructions && (
        <div>
          <p className="label mb-1">System instructions</p>
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded border border-surface-border bg-surface-1 p-2.5 font-mono text-xs text-ink-2">
            {agent.system_instructions}
          </pre>
        </div>
      )}

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 font-mono text-xs sm:grid-cols-3">
        <div>
          <dt className="text-ink-3">ID</dt>
          <dd className="text-ink-1">#{agent.id}</dd>
        </div>
        <div>
          <dt className="text-ink-3">Model</dt>
          <dd className="text-ink-1">{agent.model_name}</dd>
        </div>
        <div>
          <dt className="text-ink-3">Created</dt>
          <dd className="text-ink-1">{formatDateTime(agent.created_at)}</dd>
        </div>
        <div>
          <dt className="text-ink-3">Allowed tools</dt>
          <dd className="text-ink-1">{agent.allowed_tool_ids.length ? agent.allowed_tool_ids.join(", ") : "None"}</dd>
        </div>
        <div>
          <dt className="text-ink-3">Knowledge sources</dt>
          <dd className="text-ink-1">
            {agent.knowledge_source_ids.length ? agent.knowledge_source_ids.join(", ") : "None"}
          </dd>
        </div>
      </dl>

      <div className="space-y-3 rounded border border-surface-border bg-surface-1/40 p-3">
        <p className="label">Editable configuration</p>
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-xs text-ink-2">
            <span className="text-ink-3">Status</span>
            <select
              className="input w-auto font-mono text-xs"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="active">active</option>
              <option value="disabled">disabled</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-xs text-ink-2">
            <input
              type="checkbox"
              checked={approvalRequired}
              onChange={(e) => setApprovalRequired(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-surface-border bg-surface-3"
            />
            Require approval
          </label>
          <Button variant="primary" size="sm" onClick={handleSave} loading={saving} disabled={!dirty}>
            Save changes
          </Button>
        </div>
        {error && <InlineError message={error} />}
      </div>
    </div>
  );
}

export function AgentsPage() {
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspaces();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const load = async () => {
    if (!selectedWorkspaceId) {
      setAgents([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const list = await agentsApi.list(selectedWorkspaceId);
      setAgents(list);
      setSelectedId((current) => (current && list.some((a) => a.id === current) ? current : list[0]?.id ?? null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agents.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWorkspaceId]);

  const selected = agents.find((a) => a.id === selectedId) ?? null;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink-1">Agents</h1>
          <p className="mt-1 text-sm text-ink-3">
            {selectedWorkspace
              ? `Agent definitions scoped to ${selectedWorkspace.name}.`
              : "Agent definitions for the active workspace."}
          </p>
        </div>
        {selectedWorkspaceId && (
          <Button variant="primary" size="sm" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? <IconX className="h-3.5 w-3.5" /> : <IconPlus className="h-3.5 w-3.5" />}
            {showCreate ? "Cancel" : "New agent"}
          </Button>
        )}
      </header>

      {!selectedWorkspaceId ? (
        <EmptyState title="Select a workspace" description="Choose a workspace from the top bar to view its agents." />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <Panel className="lg:col-span-2">
            <PanelHeader
              icon={<IconBot className="h-3.5 w-3.5" />}
              title="Agent Definitions"
              meta={<span className="font-mono text-[10px] text-ink-3">{agents.length}</span>}
            />
            {showCreate && (
              <CreateAgentForm
                workspaceId={selectedWorkspaceId}
                onCreated={() => {
                  setShowCreate(false);
                  void load();
                }}
                onCancel={() => setShowCreate(false)}
              />
            )}
            <PanelBody className="p-0">
              {loading ? (
                <LoadingState />
              ) : error ? (
                <ErrorState message={error} />
              ) : agents.length === 0 ? (
                <EmptyState title="No agents in this workspace" description="Create one to start dispatching runs." />
              ) : (
                <ul className="divide-y divide-surface-border">
                  {agents.map((agent) => (
                    <li key={agent.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(agent.id)}
                        className={`flex w-full items-center justify-between gap-2 px-4 py-2.5 text-left transition-colors hover:bg-surface-3/60 ${
                          selectedId === agent.id ? "bg-brand/5" : ""
                        }`}
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium text-ink-1">{agent.name}</span>
                          <span className="block truncate font-mono text-[10px] text-ink-3">{agent.model_name}</span>
                        </span>
                        <Badge tone={agent.status === "active" ? "success" : "neutral"}>{agent.status}</Badge>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </PanelBody>
          </Panel>

          <Panel className="lg:col-span-3">
            <PanelHeader icon={<IconBot className="h-3.5 w-3.5" />} title="Agent Detail" />
            <PanelBody>
              {!selected ? (
                <EmptyState title="Select an agent" description="Pick an agent from the list to view its configuration." />
              ) : (
                <AgentDetail
                  agent={selected}
                  onUpdated={(updated) => setAgents((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))}
                />
              )}
            </PanelBody>
          </Panel>
        </div>
      )}
    </div>
  );
}