import {
  IconAlertTriangle,
  IconCheck,
  IconInbox,
  IconMail,
  IconShieldCheck,
} from "@/components/ui/Icon";
import type { FolderType, SmtpHealthStatus } from "./types";

interface MailSidebarProps {
  selectedFolder: FolderType;
  onSelectFolder: (folder: FolderType) => void;
  unreadCount: number;
  totalCount: number;
  filterUnreadOnly: boolean;
  onToggleUnreadOnly: () => void;
  smtpHealth: SmtpHealthStatus | null;
}

export function MailSidebar({
  selectedFolder,
  onSelectFolder,
  unreadCount,
  totalCount,
  filterUnreadOnly,
  onToggleUnreadOnly,
  smtpHealth,
}: MailSidebarProps) {
  const folders = [
    { key: "all" as const, label: "All Inbound", count: totalCount, icon: IconInbox },
    { key: "sent" as const, label: "Sent Messages", icon: IconMail },
    { key: "permits" as const, label: "Work Permits", icon: IconShieldCheck },
    { key: "security" as const, label: "Security Events", icon: IconAlertTriangle },
    { key: "governance" as const, label: "Four-Eyes / Gov", icon: IconCheck },
  ];

  return (
    <div className="hidden md:flex w-52 lg:w-56 border-r border-surface-border bg-surface-2/40 flex-col justify-between p-3 shrink-0">
      <div className="space-y-4">
        <div>
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink-3 px-2">
            Mailboxes
          </span>
          <div className="mt-2 space-y-1">
            {folders.map((f) => {
              const IconComponent = f.icon;
              const isActive = selectedFolder === f.key;
              return (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => onSelectFolder(f.key)}
                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-brand/15 text-brand font-semibold"
                      : "text-ink-2 hover:bg-surface-3 hover:text-ink-1"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <IconComponent className="h-4 w-4" />
                    <span>{f.label}</span>
                  </div>
                  {f.key === "all" && unreadCount > 0 && (
                    <span className="rounded-full bg-brand px-1.5 py-0.2 font-mono text-[10px] font-bold text-black">
                      {unreadCount}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <div className="border-t border-surface-border pt-3">
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink-3 px-2">
            Quick Filter
          </span>
          <button
            type="button"
            onClick={onToggleUnreadOnly}
            className={`mt-2 flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
              filterUnreadOnly
                ? "bg-blue-500/15 text-blue-400 font-semibold"
                : "text-ink-2 hover:bg-surface-3 hover:text-ink-1"
            }`}
          >
            <span>Unread Only</span>
            {unreadCount > 0 && (
              <span className="h-2 w-2 rounded-full bg-blue-400" />
            )}
          </button>
        </div>
      </div>

      {/* Transport status. Only assert what the health endpoint verified. */}
      <div className="rounded-lg border border-surface-border bg-surface-2 p-2.5 text-[11px] font-mono text-ink-3 space-y-1">
        <div className="flex items-center justify-between">
          <span>Transport scope:</span>
          <span
            className={
              smtpHealth?.loopback_only
                ? "text-emerald-400 font-bold"
                : "text-status-warning font-bold"
            }
          >
            {smtpHealth ? (smtpHealth.loopback_only ? "LOCAL ONLY" : "NOT VERIFIED") : "UNAVAILABLE"}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span>Transport:</span>
          <span className="text-ink-2">
            {smtpHealth ? `${smtpHealth.host}:${smtpHealth.port}` : "Unavailable"}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span>Internet status:</span>
          <span className="text-status-warning font-bold">NOT VERIFIED</span>
        </div>
      </div>
    </div>
  );
}
