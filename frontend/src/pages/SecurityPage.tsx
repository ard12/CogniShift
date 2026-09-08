import { useCallback, useEffect, useState } from "react";
import { securityApi, type PendingDevice } from "@/api/security";
import { useAuth } from "@/auth/useAuth";
import { useWorkspaces } from "@/context/useWorkspaces";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { IconAlertTriangle, IconCheck, IconLock, IconShieldCheck } from "@/components/ui/Icon";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import type { SecurityStatus } from "@/types";

const ITEMS: Array<[keyof SecurityStatus, string]> = [
  ["identity", "Identity"], ["device", "Device"], ["workspace", "Workspace"], ["local_ai", "Local AI"],
  ["external_internet", "External Internet"], ["sensitive_tools", "Sensitive Tools"], ["audit_logging", "Audit Logging"],
];

export function SecurityPage() {
  const { role } = useAuth();
  const { selectedWorkspaceId } = useWorkspaces();
  const [status, setStatus] = useState<SecurityStatus | null>(null);
  const [pending, setPending] = useState<PendingDevice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    if (!selectedWorkspaceId) return;
    try {
      setStatus(await securityApi.status(selectedWorkspaceId));
      if (role === "administrator") setPending(await securityApi.pendingDevices());
      setError(null);
    } catch (err) { setError(err instanceof Error ? err.message : "Security state unavailable."); }
  }, [role, selectedWorkspaceId]);
  useEffect(() => { void refresh(); }, [refresh]);
  return <div className="flex flex-col gap-6">
    <PageHeader title="Security Dashboard" description="Verified identity, device, workspace, local AI, network, approval, and audit posture." />
    {error && <div className="rounded border border-status-warning/40 bg-status-warning/10 p-3 text-xs text-status-warning">{error}</div>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {ITEMS.map(([key, label]) => {
        const item = status?.[key];
        if (!item || typeof item === "boolean") return null;
        const ok = ["verified", "trusted", "authorized", "active", "blocked", "protected"].includes(item.status);
        return <div key={key} className={`panel p-4 ${ok ? "border-status-success/30" : "border-status-warning/40"}`}>
          <div className="flex items-center gap-2 text-xs font-mono uppercase text-ink-3">{ok ? <IconCheck className="text-status-success" /> : <IconAlertTriangle className="text-status-warning" />}{label}</div>
          <p className="mt-2 text-sm font-semibold text-ink-1">{item.label}</p>
          {item.evidence && <p className="mt-1 text-[10px] text-ink-3">{item.evidence}</p>}
        </div>;
      })}
    </div>
    {role === "administrator" && <Panel>
      <PanelHeader icon={<IconShieldCheck className="h-4 w-4" />} title="Pending Device Approvals" />
      <PanelBody>
        {pending.length === 0 ? <p className="text-xs text-ink-3">No unknown devices are awaiting approval.</p> : <div className="space-y-2">{pending.map((device) => <div key={device.device_id} className="flex flex-wrap items-center gap-3 rounded border border-status-warning/30 p-3">
          <IconLock className="text-status-warning" /><div className="min-w-0 flex-1"><p className="text-xs text-ink-1">{device.display_name} · {device.user_id}</p><p className="truncate font-mono text-[10px] text-ink-3">{device.key_fingerprint}</p></div>
          <Button size="sm" onClick={async () => { await securityApi.approveDevice(device.device_id); await refresh(); }}>Approve device</Button>
        </div>)}</div>}
      </PanelBody>
    </Panel>}
  </div>;
}
