import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  securityApi,
  type PendingDevice,
  type DeviceRecord,
  type SmtpHealthStatus,
} from "@/api/security";
import { useAuth } from "@/auth/useAuth";
import { useWorkspaces } from "@/context/useWorkspaces";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { IconAlertTriangle, IconCheck, IconInbox, IconLock, IconShieldCheck } from "@/components/ui/Icon";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import type { SecurityStatus } from "@/types";

const ITEMS: Array<[keyof SecurityStatus, string]> = [
  ["identity", "Identity"], ["device", "Device"], ["workspace", "Workspace"], ["local_ai", "Local AI"],
  ["external_internet", "External Internet"], ["network_interface", "Physical Network"],
  ["docker_sandbox", "Execution Sandbox"], ["sensitive_tools", "Sensitive Tools"], ["audit_logging", "Audit Logging"],
];

export function SecurityPage() {
  const navigate = useNavigate();
  const { role } = useAuth();
  const { selectedWorkspaceId } = useWorkspaces();
  const [status, setStatus] = useState<SecurityStatus | null>(null);
  const [pending, setPending] = useState<PendingDevice[]>([]);
  const [allDevices, setAllDevices] = useState<DeviceRecord[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [smtpHealth, setSmtpHealth] = useState<SmtpHealthStatus | null>(null);
  const [isDispatching, setIsDispatching] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!selectedWorkspaceId) return;
    try {
      setStatus(await securityApi.status(selectedWorkspaceId));
      if (role === "administrator") {
        setPending(await securityApi.pendingDevices());
        setAllDevices(await securityApi.listDevices());
        try {
          const mb = await securityApi.mailbox(1, 0);
          setUnreadCount(mb.unread_count);
        } catch {
          // Ignore mailbox error if migrating
        }
        try {
          const health = await securityApi.smtpHealth();
          setSmtpHealth(health);
        } catch {
          // Ignore SMTP health error if inactive
        }
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Security state unavailable.");
    }
  }, [role, selectedWorkspaceId]);

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => {
      void refresh();
    }, 3000);
    return () => clearInterval(interval);
  }, [refresh]);

  const handleDispatchTest = async () => {
    setIsDispatching(true);
    try {
      await securityApi.dispatchTestAlert();
      await refresh();
    } catch (err) {
      console.error("Test alert dispatch failed:", err);
    } finally {
      setIsDispatching(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Security Dashboard"
        description="Verified identity, device, workspace, local AI, network, approval, and audit posture."
      />
      {error && (
        <div className="rounded border border-status-warning/40 bg-status-warning/10 p-3 text-xs text-status-warning">
          {error}
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {ITEMS.map(([key, label]) => {
          const item = status?.[key];
          if (!item || typeof item === "boolean") return null;
          const ok = ["verified", "trusted", "authorized", "active", "blocked", "protected", "connected"].includes(item.status);
          return (
            <div key={key} className={`panel p-4 ${ok ? "border-status-success/30" : "border-status-warning/40"}`}>
              <div className="flex items-center gap-2 text-xs font-mono uppercase text-ink-3">
                {ok ? <IconCheck className="text-status-success" /> : <IconAlertTriangle className="text-status-warning" />}
                {label}
              </div>
              <p className="mt-2 text-sm font-semibold text-ink-1">{item.label}</p>
              {item.evidence && <p className="mt-1 text-[10px] text-ink-3">{item.evidence}</p>}
            </div>
          );
        })}
      </div>

      {role === "administrator" && (
        <>
          {/* SOVEREIGN MAILBOX SUMMARY WIDGET */}
          <Panel>
            <PanelHeader
              icon={<IconInbox className="h-4 w-4" />}
              title={
                <div className="flex flex-wrap items-center justify-between gap-2 w-full pr-2">
                  <div className="flex items-center gap-2">
                    <span>Sovereign Mailbox & Communications</span>
                    {unreadCount > 0 && (
                      <span className="rounded-full bg-blue-500 px-2 py-0.5 text-[10px] font-bold text-white">
                        {unreadCount} UNREAD
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[11px] font-normal">
                    {smtpHealth?.status === "ACTIVE" ? (
                      <span className="flex items-center gap-1.5 rounded bg-emerald-500/10 px-2 py-0.5 font-mono text-emerald-400 border border-emerald-500/20">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        LOCAL SMTP ACTIVE: 127.0.0.1:1025 (LOOPBACK ONLY)
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 rounded bg-status-error/10 px-2 py-0.5 font-mono text-status-error border border-status-error/20">
                        <span className="h-1.5 w-1.5 rounded-full bg-status-error" />
                        LOCAL SMTP UNAVAILABLE
                      </span>
                    )}
                  </div>
                </div>
              }
            />
            <PanelBody>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-1">
                  <p className="text-xs text-ink-2 font-medium">
                    Role-scoped secure sovereign notifications, Four-Eyes work permits, and governance dispatches.
                  </p>
                  <p className="text-[11px] text-ink-3">
                    Mail is isolated per recipient. Aryan, Supervisors, and Admin have independent mailboxes and read states.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={isDispatching}
                    onClick={handleDispatchTest}
                  >
                    {isDispatching ? "Dispatching..." : "Dispatch Test Alert"}
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => navigate("/mailbox")}
                  >
                    Open Sovereign Mailbox
                  </Button>
                </div>
              </div>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader icon={<IconShieldCheck className="h-4 w-4" />} title="Pending Device Approvals" />
            <PanelBody>
              {pending.length === 0 ? (
                <p className="text-xs text-ink-3">No unknown devices are awaiting approval.</p>
              ) : (
                <div className="space-y-3">
                  {pending.map((device) => (
                    <div
                      key={`${device.device_id}:${device.user_id}`}
                      className="flex flex-wrap items-center justify-between gap-3 rounded border border-status-warning/40 bg-surface-2 p-3"
                    >
                      <div className="flex items-start gap-3 min-w-0 flex-1">
                        <IconLock className="mt-1 h-4 w-4 shrink-0 text-status-warning" />
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-xs text-ink-1">
                              {device.display_name} <span className="font-normal text-ink-3">(declared metadata)</span>
                            </span>
                            <span className="rounded bg-status-warning/15 px-1.5 py-0.5 font-mono text-[10px] text-status-warning font-medium">
                              PENDING APPROVAL
                            </span>
                          </div>
                          <p className="font-mono text-xs text-brand font-medium">User: {device.user_id}</p>
                          <p className="font-mono text-[11px] text-ink-2">Remote IP: {device.last_ip || "Unknown IP"}</p>
                          <p className="truncate font-mono text-[10px] text-ink-3" title={device.key_fingerprint}>
                            Key Fingerprint: {device.key_fingerprint}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={async () => {
                            await securityApi.approveDevice(device.device_id, device.user_id);
                            await refresh();
                          }}
                        >
                          Approve Device
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          className="border-status-error/40 text-status-error hover:bg-status-error/10"
                          onClick={async () => {
                            await securityApi.blockDevice(device.device_id, device.user_id);
                            await refresh();
                          }}
                        >
                          Block Device
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader icon={<IconShieldCheck className="h-4 w-4" />} title="All Managed Terminal Devices" />
            <PanelBody>
              {allDevices.length === 0 ? (
                <p className="text-xs text-ink-3">No devices registered in database.</p>
              ) : (
                <div className="space-y-2">
                  {allDevices.map((device) => {
                    const isApproved = device.status === "approved";
                    const isBlocked = device.status === "blocked";
                    const isRevoked = device.status === "revoked";
                    return (
                      <div
                        key={device.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded border border-surface-border bg-surface-2 p-3"
                      >
                        <div className="min-w-0 flex-1 space-y-0.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-xs text-ink-1">
                              {device.display_name} <span className="text-ink-3 font-normal">(declared metadata)</span>
                            </span>
                            <span
                              className={`rounded px-1.5 py-0.5 font-mono text-[10px] uppercase font-bold ${
                                isApproved
                                  ? "bg-status-success/15 text-status-success"
                                  : isBlocked
                                  ? "bg-status-error/15 text-status-error"
                                  : isRevoked
                                  ? "bg-status-warning/15 text-status-warning"
                                  : "bg-surface-3 text-ink-3"
                              }`}
                            >
                              {device.status}
                            </span>
                          </div>
                          <p className="font-mono text-xs text-ink-2">
                            User: <span className="font-semibold text-ink-1">{device.user_id}</span> · IP: {device.last_ip || "—"}
                          </p>
                          <p className="truncate font-mono text-[10px] text-ink-3" title={device.key_fingerprint}>
                            Fingerprint: {device.key_fingerprint}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {isApproved && (
                            <>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={async () => {
                                  await securityApi.revokeDevice(device.device_id, device.user_id);
                                  await refresh();
                                }}
                              >
                                Revoke
                              </Button>
                              <Button
                                size="sm"
                                variant="secondary"
                                className="border-status-error/40 text-status-error hover:bg-status-error/10"
                                onClick={async () => {
                                  await securityApi.blockDevice(device.device_id, device.user_id);
                                  await refresh();
                                }}
                              >
                                Block
                              </Button>
                            </>
                          )}
                          {(isRevoked || isBlocked) && (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={async () => {
                                await securityApi.approveDevice(device.device_id, device.user_id);
                                await refresh();
                              }}
                            >
                              Re-Approve
                            </Button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </PanelBody>
          </Panel>
        </>
      )}
    </div>
  );
}
