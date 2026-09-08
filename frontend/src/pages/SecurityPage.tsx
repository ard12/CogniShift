import { useCallback, useEffect, useState } from "react";
import {
  securityApi,
  type PendingDevice,
  type DeviceRecord,
  type SecurityAlert,
  type SecurityAlertDetail,
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
  const { role } = useAuth();
  const { selectedWorkspaceId } = useWorkspaces();
  const [status, setStatus] = useState<SecurityStatus | null>(null);
  const [pending, setPending] = useState<PendingDevice[]>([]);
  const [allDevices, setAllDevices] = useState<DeviceRecord[]>([]);
  const [alerts, setAlerts] = useState<SecurityAlert[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [selectedAlert, setSelectedAlert] = useState<SecurityAlertDetail | null>(null);
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
          const mb = await securityApi.mailbox(50, 0);
          setAlerts(mb.alerts);
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

  const handleOpenAlert = async (alertId: number) => {
    try {
      const detail = await securityApi.alertDetail(alertId);
      setSelectedAlert(detail);
      if (!detail.is_read) {
        await securityApi.markAlertRead(alertId);
        setAlerts((prev) =>
          prev.map((a) => (a.id === alertId ? { ...a, is_read: 1 } : a))
        );
        setUnreadCount((c) => Math.max(0, c - 1));
      }
    } catch (err) {
      console.error("Failed to load alert detail:", err);
    }
  };

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

  const handleClearMailbox = async () => {
    if (!window.confirm("Purge all security alerts in SOC mailbox?")) return;
    try {
      await securityApi.clearMailbox();
      await refresh();
    } catch (err) {
      console.error("Clear mailbox failed:", err);
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case "CRITICAL":
        return "bg-status-error/15 text-status-error border border-status-error/30";
      case "HIGH":
        return "bg-orange-500/15 text-orange-400 border border-orange-500/30";
      case "MEDIUM":
        return "bg-status-warning/15 text-status-warning border border-status-warning/30";
      case "LOW":
      default:
        return "bg-blue-500/15 text-blue-400 border border-blue-500/30";
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
          {/* SOC SECURITY INBOX PANEL */}
          <Panel>
            <PanelHeader
              icon={<IconInbox className="h-4 w-4" />}
              title={
                <div className="flex flex-wrap items-center justify-between gap-2 w-full pr-2">
                  <div className="flex items-center gap-2">
                    <span>SOC Security Mailbox</span>
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
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-ink-3">
                  Sovereign telemetry notifications and Four-Eyes governance dispatches.
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={isDispatching}
                    onClick={handleDispatchTest}
                  >
                    {isDispatching ? "Dispatching..." : "Dispatch Test Alert"}
                  </Button>
                  {alerts.length > 0 && (
                    <Button
                      size="sm"
                      variant="secondary"
                      className="border-status-error/40 text-status-error hover:bg-status-error/10"
                      onClick={handleClearMailbox}
                    >
                      Clear Mailbox
                    </Button>
                  )}
                </div>
              </div>

              {alerts.length === 0 ? (
                <div className="rounded border border-surface-border bg-surface-2 p-6 text-center text-xs text-ink-3">
                  Security mailbox is empty. Incoming security interceptions and governance events will appear here in real time.
                </div>
              ) : (
                <div className="divide-y divide-surface-border rounded border border-surface-border bg-surface-2 overflow-hidden">
                  {alerts.map((alert) => (
                    <div
                      key={alert.id}
                      onClick={() => void handleOpenAlert(alert.id)}
                      className={`flex flex-wrap items-center justify-between gap-3 p-3 transition-colors cursor-pointer hover:bg-surface-3/60 ${
                        !alert.is_read ? "bg-blue-500/5 font-medium" : ""
                      }`}
                    >
                      <div className="flex items-start gap-3 min-w-0 flex-1">
                        <div className="mt-1">
                          {!alert.is_read ? (
                            <span className="block h-2 w-2 rounded-full bg-blue-400" title="Unread" />
                          ) : (
                            <span className="block h-2 w-2 rounded-full bg-surface-border" title="Read" />
                          )}
                        </div>
                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`rounded px-1.5 py-0.2 font-mono text-[10px] font-bold uppercase ${getSeverityBadge(alert.severity)}`}>
                              {alert.severity}
                            </span>
                            <span className="rounded bg-surface-3 px-1.5 py-0.2 font-mono text-[10px] text-ink-3">
                              {alert.alert_type}
                            </span>
                            <span className="text-xs font-semibold text-ink-1 truncate">
                              {alert.subject}
                            </span>
                          </div>
                          <p className="text-[11px] text-ink-3 font-mono">
                            From: <span className="text-ink-2">{alert.sender}</span> · To: <span className="text-ink-2">{alert.recipients.join(", ")}</span>
                            {alert.related_user && (
                              <> · User: <span className="text-brand font-semibold">{alert.related_user}</span></>
                            )}
                            {alert.related_ip && (
                              <> · IP: <span className="text-sky-400">{alert.related_ip}</span></>
                            )}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="font-mono text-[10px] text-ink-3">
                          {new Date(alert.created_at).toLocaleTimeString()}
                        </span>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleOpenAlert(alert.id);
                          }}
                        >
                          Inspect
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </PanelBody>
          </Panel>

          {/* ALERT INSPECTION MODAL */}
          {selectedAlert && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
              <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl border border-surface-border bg-surface-1 p-6 shadow-2xl">
                <div className="flex items-center justify-between border-b border-surface-border pb-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={`rounded px-2 py-0.5 font-mono text-[11px] font-bold uppercase ${getSeverityBadge(selectedAlert.severity)}`}>
                        {selectedAlert.severity}
                      </span>
                      <span className="rounded bg-surface-3 px-2 py-0.5 font-mono text-[11px] text-ink-3">
                        {selectedAlert.alert_type}
                      </span>
                      <span className="font-mono text-[10px] text-ink-3">
                        Mode: {selectedAlert.composition_mode}
                      </span>
                    </div>
                    <h3 className="text-base font-bold text-ink-1">{selectedAlert.subject}</h3>
                    <p className="font-mono text-xs text-ink-3">
                      Dispatched: {new Date(selectedAlert.created_at).toLocaleString()} via Local Loopback
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setSelectedAlert(null)}
                  >
                    Close
                  </Button>
                </div>

                <div className="mt-4 space-y-4">
                  {/* Telemetry metadata table */}
                  <div className="rounded border border-surface-border bg-surface-2 p-3">
                    <h4 className="font-mono text-[10px] uppercase tracking-wider text-ink-3 mb-2 font-bold">
                      Telemetry & Authentication Context
                    </h4>
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                      <div><span className="text-ink-3">Target User:</span> <span className="text-brand font-semibold">{selectedAlert.related_user || "N/A"}</span></div>
                      <div><span className="text-ink-3">Origin IP:</span> <span className="text-sky-400">{selectedAlert.related_ip || "N/A"}</span></div>
                      <div><span className="text-ink-3">Device ID:</span> <span className="text-ink-2 truncate">{selectedAlert.related_device_id || "N/A"}</span></div>
                      <div><span className="text-ink-3">Run ID:</span> <span className="text-ink-2">{selectedAlert.related_run_id ? `#${selectedAlert.related_run_id}` : "N/A"}</span></div>
                    </div>
                  </div>

                  {/* Body Text / Narrative */}
                  <div className="space-y-2">
                    <h4 className="font-mono text-[10px] uppercase tracking-wider text-ink-3 font-bold">
                      Notification Body
                    </h4>
                    <div className="rounded border border-surface-border bg-surface-2 p-4 font-mono text-xs leading-relaxed text-ink-1 whitespace-pre-wrap">
                      {selectedAlert.body_text}
                    </div>
                  </div>

                  {/* Verified Citations */}
                  <div className="space-y-2">
                    <h4 className="font-mono text-[10px] uppercase tracking-wider text-ink-3 font-bold">
                      Authoritative Grounding Citations ({selectedAlert.citations?.length || 0})
                    </h4>
                    {(!selectedAlert.citations || selectedAlert.citations.length === 0) ? (
                      <p className="text-xs text-ink-3">No external citations attached.</p>
                    ) : (
                      <div className="space-y-2">
                        {selectedAlert.citations.map((c) => (
                          <div
                            key={c.id}
                            className="flex items-center justify-between rounded border border-surface-border bg-surface-2 px-3 py-2 text-xs"
                          >
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-bold text-ink-1">[{c.citation_index}]</span>
                                <span className="rounded bg-surface-3 px-1.5 py-0.2 font-mono text-[10px] text-ink-2">
                                  {c.citation_class}
                                </span>
                                <span className="font-semibold text-ink-1">{c.display_label}</span>
                              </div>
                              <p className="font-mono text-[10px] text-ink-3">
                                Source ID: {c.source_id} {c.page_number ? `· Page ${c.page_number}` : ""}
                              </p>
                            </div>
                            <span className="rounded bg-emerald-500/15 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-400 border border-emerald-500/30">
                              VERIFIED
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-6 flex items-center justify-end border-t border-surface-border pt-4">
                  <Button
                    variant="primary"
                    onClick={() => setSelectedAlert(null)}
                  >
                    Done
                  </Button>
                </div>
              </div>
            </div>
          )}

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
