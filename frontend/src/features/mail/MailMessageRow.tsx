import { formatRelativeTime } from "@/lib/format";
import { getSeverityBadge } from "./mailUtils";
import type { MailMessageMetadata } from "./types";

interface MailMessageRowProps {
  message: MailMessageMetadata;
  isSelected: boolean;
  onSelect: (id: number) => void;
}

export function MailMessageRow({
  message,
  isSelected,
  onSelect,
}: MailMessageRowProps) {
  return (
    <div
      onClick={() => onSelect(message.id)}
      className={`p-3 transition-colors cursor-pointer text-left ${
        isSelected
          ? "bg-brand/10 border-l-2 border-brand"
          : message.is_read
          ? "hover:bg-surface-2"
          : "bg-blue-500/5 hover:bg-surface-2 font-medium"
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-1.5 min-w-0">
          {!message.is_read ? (
            <span className="h-2 w-2 rounded-full bg-blue-400 shrink-0" title="Unread" />
          ) : (
            <span className="h-2 w-2 rounded-full bg-transparent shrink-0" />
          )}
          <span className="truncate text-xs font-semibold text-ink-1">
            {message.sender.split("@")[0]}
          </span>
        </div>
        <span className="font-mono text-[10px] text-ink-3 shrink-0">
          {formatRelativeTime(message.created_at)}
        </span>
      </div>

      <div className="flex items-center gap-1.5 mb-1">
        <span
          className={`rounded px-1.5 py-0.2 font-mono text-[9px] font-bold uppercase ${getSeverityBadge(
            message.severity
          )}`}
        >
          {message.severity}
        </span>
        <span className="rounded bg-surface-3 px-1.5 py-0.2 font-mono text-[9px] text-ink-3 truncate">
          {message.alert_type}
        </span>
      </div>

      <p className="text-xs text-ink-2 truncate font-medium">{message.subject}</p>
      {message.related_user && (
        <p className="text-[10px] font-mono text-ink-3 mt-1">
          Operator: <span className="text-brand font-medium">{message.related_user}</span>
        </p>
      )}
    </div>
  );
}
