import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { agentsApi } from "@/api/agents";
import { ApiError } from "@/api/clients";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  IconBot,
  IconCheck,
  IconCopy,
  IconPlay,
  IconPlayCircle,
  IconPlus,
  IconX,
} from "@/components/ui/Icon";
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

interface SuggestedPrompt {
  id: string;
  title: string;
  badge: string;
  badgeTone: "neutral" | "info" | "warning" | "danger" | "success";
  text: string;
}

function getSuggestedPromptsForAgent(agent: Agent): SuggestedPrompt[] {
  const prompts: SuggestedPrompt[] = [];
  const model = (agent.model_name || "").toLowerCase();
  const name = (agent.name || "").toLowerCase();
  const desc = (agent.description || "").toLowerCase();
  const instructions = (agent.system_instructions || "").toLowerCase();
  const tools = agent.allowed_tool_ids || [];

  const isCoder =
    model.includes("coder") ||
    name.includes("coder") ||
    name.includes("code") ||
    name.includes("developer") ||
    name.includes("python") ||
    desc.includes("code") ||
    desc.includes("python") ||
    tools.includes(15);

  const isVision =
    model.includes("moondream") ||
    model.includes("vision") ||
    name.includes("vision") ||
    name.includes("gauge") ||
    name.includes("inspection") ||
    desc.includes("vision") ||
    desc.includes("camera");

  const isFinancial =
    name.includes("finance") ||
    name.includes("financial") ||
    name.includes("cagr") ||
    name.includes("yoy") ||
    name.includes("revenue") ||
    name.includes("ebitda") ||
    desc.includes("financial") ||
    instructions.includes("yoy");

  const isIT =
    name.includes("it") ||
    name.includes("helpdesk") ||
    name.includes("network") ||
    tools.includes(6) ||
    tools.includes(7);

  if (isCoder) {
    prompts.push(
      {
        id: "coder-threshold-filter",
        title: "Telemetry Outlier Filtering (Docker Sandbox)",
        badge: "DOCKER SANDBOX",
        badgeTone: "info",
        text: "Write a Python script to filter sensor readings from a list of values [102.1, 495.3, 98.4, 510.2, 101.0] that exceed the safe operating threshold of 450 PSI, and execute it in the sandbox.",
      },
      {
        id: "coder-vibration-stats",
        title: "Vibration Standard Deviation Analysis",
        badge: "DOCKER SANDBOX",
        badgeTone: "info",
        text: "Generate and execute a Python script to calculate the mean and standard deviation for the last 10 hourly vibration readings on Pump-101A.",
      },
      {
        id: "coder-data-validation",
        title: "Dataset Sanitization & NaN Assertion",
        badge: "DATA VALIDATION",
        badgeTone: "neutral",
        text: "Write and execute a Python script to inspect telemetry records and verify that all pressure transmitter readings are strictly non-negative and finite.",
      }
    );
  } else if (isVision) {
    prompts.push(
      {
        id: "vision-analog-dial",
        title: "Analog Gauge Dial Reading (PT-101)",
        badge: "VISION OCR",
        badgeTone: "warning",
        text: "Inspect the attached analog pressure gauge dial image for sensor PT-101. Report the pointer needle angle, reading in PSI, and confirm if it breaches the 450 PSI threshold.",
      },
      {
        id: "vision-faceplate-scale",
        title: "Faceplate Calibration & Unit Verification",
        badge: "INSPECTION",
        badgeTone: "neutral",
        text: "Examine the meter faceplate for instrument tag markings and verify whether the primary dial scale is calibrated in PSI or bar.",
      },
      {
        id: "vision-negative-abstention",
        title: "Non-Instrument Imagery Safety Abstention",
        badge: "SAFETY REFUSAL",
        badgeTone: "neutral",
        text: "Analyze this image. If it does not contain an industrial dial, meter, or process instrument, state that clearly and refuse measurement.",
      }
    );
  } else if (isFinancial) {
    prompts.push(
      {
        id: "fin-strict-yoy",
        title: "Strict YoY Financial Verification (GoalContract)",
        badge: "GOAL CONTRACT",
        badgeTone: "neutral",
        text: "Calculate the Year-over-Year (YoY) revenue and EBITDA growth percentages from the Q4 financials. Do not substitute CAGR values.",
      },
      {
        id: "fin-ebitda-variance",
        title: "EBITDA Margin & Variance Evaluation",
        badge: "ANALYTICS",
        badgeTone: "neutral",
        text: "Extract operating revenues and EBITDA for FY2023 vs FY2024 and evaluate the percentage margin variance.",
      },
      {
        id: "fin-capex-depreciation",
        title: "CapEx & Asset Depreciation Summary",
        badge: "REPORT",
        badgeTone: "info",
        text: "Review capital expenditure allocations and summarize depreciation schedules for newly commissioned refinery units.",
      }
    );
  } else if (isIT) {
    prompts.push(
      {
        id: "it-gateway-ping",
        title: "SCADA Gateway Connectivity Check",
        badge: "READ-ONLY",
        badgeTone: "neutral",
        text: "Check network connectivity to SCADA gateway 192.168.40.10 and report packet latency.",
      },
      {
        id: "it-restart-bridge",
        title: "Restart Telemetry Bridge Service",
        badge: "SUPERVISOR PERMIT",
        badgeTone: "warning",
        text: "The Modbus collector service telemetry-bridge is unresponsive. Initiate restart for service telemetry-bridge.",
      },
      {
        id: "it-vlan-audit",
        title: "VLAN 40 Telemetry Port Audit",
        badge: "DIAGNOSTIC",
        badgeTone: "neutral",
        text: "Verify open telemetry ports on VLAN 40 and check that port 502 Modbus/TCP is actively listening.",
      }
    );
  } else {
    // Standard refinery / operations / multi-step diagnostic specialist
    prompts.push(
      {
        id: "ops-pt101-sop",
        title: "PT-101 Nominal Operating Window & Telemetry",
        badge: "READ-ONLY",
        badgeTone: "neutral",
        text: "What is the normal operating pressure for sensor PT-101 according to our SOP? Please check current pressure telemetry.",
      },
      {
        id: "ops-emergency-relief",
        title: "Overpressure Excursion & Four-Eyes Relief",
        badge: "FOUR-EYES REQUIRED",
        badgeTone: "danger",
        text: "Pressure transmitter PT-101 is reading 495 PSI! This exceeds 450 PSI! Actuate emergency pressure relief on chamber Reactor-B!",
      },
      {
        id: "ops-tt204-diagnostic",
        title: "Thermocouple TT-204 & Bearing Diagnostics",
        badge: "DIAGNOSTIC",
        badgeTone: "neutral",
        text: "Please check temperature telemetry on thermocouple TT-204 and run equipment diagnostic on Pump-101A.",
      }
    );

    if (tools.includes(5) || instructions.includes("restart")) {
      prompts.push({
        id: "ops-restart-pump",
        title: "Post-Trip Controlled Restart (P-101A)",
        badge: "FOUR-EYES REQUIRED",
        badgeTone: "warning",
        text: "Bearing temperatures have stabilized below 70°C. Initiate controlled component restart on pump P-101A following SOP section 2.0.",
      });
    }
  }

  return prompts;
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
  const [modelName, setModelName] = useState("qwen2.5:7b");
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
          <select
            id="ag-model"
            className="input font-mono"
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
          >
            <option value="qwen2.5:7b">qwen2.5:7b (Recommended - 7B Reasoning)</option>
            <option value="llama3.2:3b">llama3.2:3b (Lightweight 3B)</option>
          </select>
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
  const navigate = useNavigate();
  const [status, setStatus] = useState(agent.status);
  const [approvalRequired, setApprovalRequired] = useState(agent.approval_required);
  const [modelName, setModelName] = useState(agent.model_name || "qwen2.5:7b");
  const [systemInstructions, setSystemInstructions] = useState(agent.system_instructions || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedPromptId, setCopiedPromptId] = useState<string | null>(null);

  const suggestedPrompts = getSuggestedPromptsForAgent(agent);

  function handleCopyPrompt(prompt: SuggestedPrompt) {
    void navigator.clipboard.writeText(prompt.text);
    setCopiedPromptId(prompt.id);
    setTimeout(() => setCopiedPromptId(null), 2000);
  }

  function handleRunInConsole(prompt: SuggestedPrompt) {
    if (agent.workspace_id) {
      sessionStorage.setItem(`cognishift_operator_prompt_${agent.workspace_id}`, prompt.text);
      sessionStorage.setItem(`cognishift_operator_agent_${agent.workspace_id}`, String(agent.id));
    }
    navigate("/operator");
  }

  useEffect(() => {
    setStatus(agent.status);
    setApprovalRequired(agent.approval_required);
    setModelName(agent.model_name || "qwen2.5:7b");
    setSystemInstructions(agent.system_instructions || "");
  }, [agent]);

  const dirty =
    status !== agent.status ||
    approvalRequired !== agent.approval_required ||
    modelName !== agent.model_name ||
    systemInstructions !== (agent.system_instructions || "");

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const updated = await agentsApi.update(agent.id, {
        status,
        approval_required: approvalRequired,
        model_name: modelName.trim() || undefined,
        system_instructions: systemInstructions.trim() || null,
      });
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

      <div>
        <div className="flex items-center justify-between mb-1">
          <p className="label">System instructions</p>
          {!agent.system_instructions && (
            <span className="text-[10px] text-amber-400 font-mono">Not configured</span>
          )}
        </div>
        {agent.system_instructions ? (
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded border border-surface-border bg-surface-1 p-2.5 font-mono text-xs text-ink-2">
            {agent.system_instructions}
          </pre>
        ) : (
          <div className="rounded border border-dashed border-surface-border bg-surface-1/40 p-3 text-xs italic text-ink-3">
            No system instructions configured for this agent. You can add operational guidelines in the configuration editor below.
          </div>
        )}
      </div>

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

      {/* Suggested Operational Prompts */}
      <div className="space-y-3 rounded border border-surface-border bg-surface-1/60 p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <IconPlayCircle className="h-4 w-4 text-brand" />
            <p className="label font-semibold text-ink-1">Operational Prompts &amp; Test Triggers</p>
          </div>
          <span className="font-mono text-[10px] text-ink-3">
            {suggestedPrompts.length} templates
          </span>
        </div>
        <p className="text-xs text-ink-3">
          Pre-validated operational prompts tailored to this agent&apos;s capabilities. Test them in the Console with 1-click execution.
        </p>

        <div className="space-y-2">
          {suggestedPrompts.map((p) => (
            <div
              key={p.id}
              className="rounded border border-surface-border/80 bg-surface-2/70 p-3 transition-colors hover:border-surface-border"
            >
              <div className="mb-1.5 flex items-start justify-between gap-2">
                <span className="text-xs font-semibold text-ink-1">{p.title}</span>
                <Badge tone={p.badgeTone}>{p.badge}</Badge>
              </div>
              <p className="select-all break-words rounded border border-surface-border/50 bg-surface-1/90 p-2 font-mono text-xs text-ink-2">
                {p.text}
              </p>
              <div className="mt-2 flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => handleCopyPrompt(p)}
                  className="text-xs"
                >
                  {copiedPromptId === p.id ? (
                    <>
                      <IconCheck className="h-3.5 w-3.5 text-status-success" />
                      <span className="text-status-success">Copied</span>
                    </>
                  ) : (
                    <>
                      <IconCopy className="h-3.5 w-3.5" />
                      Copy
                    </>
                  )}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => handleRunInConsole(p)}
                  className="text-xs"
                >
                  <IconPlay className="h-3.5 w-3.5 text-brand" />
                  ▶ Run in Console
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-3 rounded border border-surface-border bg-surface-1/40 p-3">
        <div className="flex items-center justify-between">
          <p className="label">Editable configuration</p>
          {dirty && (
            <span className="text-[10px] text-amber-400 font-mono">Unsaved changes</span>
          )}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label className="label mb-1 block">Model</label>
            <select
              className="input font-mono text-xs"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
            >
              <option value="qwen2.5:7b">qwen2.5:7b (Recommended - 7B Reasoning)</option>
              <option value="llama3.2:3b">llama3.2:3b (Lightweight 3B)</option>
            </select>
          </div>
          <div>
            <label className="label mb-1 block">Status</label>
            <select
              className="input font-mono text-xs"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="active">active</option>
              <option value="disabled">disabled</option>
            </select>
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 text-xs text-ink-2">
              <input
                type="checkbox"
                checked={approvalRequired}
                onChange={(e) => setApprovalRequired(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-surface-border bg-surface-3"
              />
              Require approval
            </label>
          </div>
        </div>

        <div>
          <label className="label mb-1 block">System instructions</label>
          <textarea
            rows={4}
            className="textarea font-mono text-xs"
            value={systemInstructions}
            onChange={(e) => setSystemInstructions(e.target.value)}
            placeholder="Enter operational rules, safety boundaries, or role guidelines..."
          />
        </div>

        <div className="flex items-center justify-between pt-1">
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