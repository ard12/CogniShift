import { useEffect, useState } from "react";
import { systemApi } from "@/api/system";
import { useAuth } from "@/auth/useAuth";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconCpu, IconRefresh, IconShieldCheck, IconWifiOff } from "@/components/ui/Icon";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { formatBytes, formatDateTime, titleCase } from "@/lib/format";
import type { NetworkEvent, PrivacyStatus, SystemStatus } from "@/types";

export function SystemPage() {
  const { sovereignty, refreshSovereignty } = useAuth();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [privacy, setPrivacy] = useState<PrivacyStatus | null>(null);
  const [events, setEvents] = useState<NetworkEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusRes, privacyRes, eventsRes] = await Promise.all([
        systemApi.status(),
        systemApi.privacyStatus(),
        systemApi.networkEvents({ limit: 25 }).catch(() => null),
      ]);
      setStatus(statusRes);
      setPrivacy(privacyRes);
      setEvents(eventsRes?.events ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load system status.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  async function handleRefresh() {
    setRefreshing(true);
    await Promise.all([load(), refreshSovereignty()]);
    setRefreshing(false);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="System & Sovereignty"
        description="Local infrastructure health, air-gap enforcement, and the outbound network audit trail."
        actions={
          <Button variant="secondary" size="sm" onClick={() => void handleRefresh()} loading={refreshing}>
            <IconRefresh className="h-3.5 w-3.5" /> Refresh
          </Button>
        }
      />

      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Panel>
            <PanelHeader icon={<IconCpu className="h-3.5 w-3.5" />} title="System Status" />
            <PanelBody className="space-y-4">
              {status && (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 font-mono text-xs">
                  <div>
                    <dt className="text-ink-3">Operating mode</dt>
                    <dd className="text-ink-1">{status.operating_mode}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">Version</dt>
                    <dd className="text-ink-1">{status.version}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">Ollama runtime</dt>
                    <dd>
                      <Badge tone={status.ollama_available ? "success" : "danger"}>
                        {status.ollama_available ? "Available" : "Unavailable"}
                      </Badge>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">Database</dt>
                    <dd>
                      <Badge tone={status.database_initialized ? "success" : "danger"}>
                        {status.database_initialized ? "Initialized" : "Not initialized"}
                      </Badge>
                    </dd>
                  </div>
                </dl>
              )}

              {privacy && (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-t border-surface-border pt-3 font-mono text-xs">
                  <div>
                    <dt className="text-ink-3">External APIs</dt>
                    <dd>
                      <Badge tone={privacy.external_apis_blocked ? "success" : "danger"}>
                        {privacy.external_apis_blocked ? "Blocked" : "Not blocked"}
                      </Badge>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">Data directory</dt>
                    <dd className="truncate text-ink-1">{privacy.data_directory}</dd>
                  </div>
                </dl>
              )}

              <div>
                <p className="label mb-2">Local models ({status?.available_models.length ?? 0})</p>
                {!status || status.available_models.length === 0 ? (
                  <p className="text-xs text-ink-3">No local models detected.</p>
                ) : (
                  <ul className="space-y-1.5 font-mono text-xs">
                    {status.available_models.map((model) => (
                      <li
                        key={model.name}
                        className="flex items-center justify-between rounded border border-surface-border bg-surface-1/40 px-2.5 py-1.5"
                      >
                        <span className="truncate text-ink-1">{model.name}</span>
                        {typeof model.size === "number" && (
                          <span className="shrink-0 text-ink-3">{formatBytes(model.size)}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader icon={<IconShieldCheck className="h-3.5 w-3.5" />} title="Sovereignty Enforcement" />
            <PanelBody className="space-y-4">
              {!sovereignty ? (
                <EmptyState title="Sovereignty status unavailable" />
              ) : (
                <>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-3 font-mono text-xs">
                    <div>
                      <dt className="text-ink-3">Policy mode</dt>
                      <dd className="text-ink-1">{sovereignty.policy_mode}</dd>
                    </div>
                    <div>
                      <dt className="text-ink-3">Your role</dt>
                      <dd className="text-ink-1">{sovereignty.user_role}</dd>
                    </div>
                    <div>
                      <dt className="text-ink-3">Sovereignty enforced</dt>
                      <dd>
                        <Badge tone={sovereignty.sovereignty_enforced ? "success" : "warning"}>
                          {sovereignty.sovereignty_enforced ? "Yes" : "No"}
                        </Badge>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-ink-3">Public egress</dt>
                      <dd>
                        <Badge tone={sovereignty.public_egress_allowed ? "warning" : "success"}>
                          {sovereignty.public_egress_allowed ? "Allowed" : "Blocked"}
                        </Badge>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-ink-3">Allowed destinations</dt>
                      <dd className="text-ink-1">{sovereignty.allowed_destinations_count}</dd>
                    </div>
                    <div>
                      <dt className="text-ink-3">Blocked attempts</dt>
                      <dd className="text-ink-1">{sovereignty.total_blocked_attempts}</dd>
                    </div>
                  </dl>

                  <div>
                    <p className="label mb-2">Component readiness</p>
                    <ul className="space-y-1.5">
                      {Object.entries(sovereignty.components).map(([name, comp]) => (
                        <li
                          key={name}
                          className="flex items-center justify-between rounded border border-surface-border bg-surface-1/40 px-2.5 py-1.5 font-mono text-xs"
                        >
                          <span className="text-ink-1">{titleCase(name)}</span>
                          <div className="flex items-center gap-2">
                            {comp.details && <span className="text-[10px] text-ink-3">{comp.details}</span>}
                            <Badge tone={comp.is_ready ? "success" : "danger"}>{comp.status}</Badge>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                </>
              )}
            </PanelBody>
          </Panel>

          <Panel className="xl:col-span-2">
            <PanelHeader icon={<IconWifiOff className="h-3.5 w-3.5" />} title="Network Audit Trail" />
            <PanelBody className="p-0">
              {events.length === 0 ? (
                <EmptyState
                  icon={<IconWifiOff className="h-6 w-6" />}
                  title="No network events recorded"
                  description="Outbound connection attempts made by CogniShift components will appear here."
                />
              ) : (
                <div className="max-h-96 overflow-y-auto">
                  <table className="w-full text-left font-mono text-xs">
                    <thead className="sticky top-0 bg-surface-2 text-[10px] uppercase tracking-wide text-ink-3">
                      <tr>
                        <th className="px-4 py-2 font-medium">Time</th>
                        <th className="px-4 py-2 font-medium">Component</th>
                        <th className="px-4 py-2 font-medium">Host</th>
                        <th className="px-4 py-2 font-medium">Class</th>
                        <th className="px-4 py-2 font-medium">Decision</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border">
                      {events.map((event) => (
                        <tr key={event.id}>
                          <td className="whitespace-nowrap px-4 py-2 text-ink-3">
                            {formatDateTime(event.timestamp)}
                          </td>
                          <td className="px-4 py-2 text-ink-1">{event.component}</td>
                          <td className="max-w-[220px] truncate px-4 py-2 text-ink-1">{event.requested_host}</td>
                          <td className="px-4 py-2 text-ink-3">{event.destination_class}</td>
                          <td className="px-4 py-2">
                            <Badge tone={event.policy_decision === "ALLOWED" ? "success" : "danger"}>
                              {event.policy_decision}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </PanelBody>
          </Panel>
        </div>
      )}
    </div>
  );
}
