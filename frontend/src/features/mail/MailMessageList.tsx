import { IconLoader } from "@/components/ui/Icon";
import { Button } from "@/components/ui/Button";
import { MailMessageRow } from "./MailMessageRow";
import type { MailMessageMetadata } from "./types";

interface MailMessageListProps {
  messages: MailMessageMetadata[];
  selectedMessageId: number | null;
  onSelectMessage: (id: number) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  isLoading: boolean;
  fetchError: string | null;
  onRetry: () => void;
}

export function MailMessageList({
  messages,
  selectedMessageId,
  onSelectMessage,
  searchQuery,
  onSearchChange,
  isLoading,
  fetchError,
  onRetry,
}: MailMessageListProps) {
  return (
    <div
      className={`${
        selectedMessageId !== null ? "hidden md:flex" : "flex"
      } w-full md:w-80 lg:w-96 border-r border-surface-border flex-col bg-surface-1 shrink-0`}
    >
      <div className="p-2.5 border-b border-surface-border">
        <input
          type="text"
          placeholder="Search subjects, users, permits..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-xs text-ink-1 placeholder:text-ink-3 focus:border-brand focus:outline-none"
        />
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-surface-border">
        {isLoading ? (
          <div className="flex h-32 items-center justify-center text-xs text-ink-3 gap-2">
            <IconLoader className="h-4 w-4 animate-spin text-brand" />
            Loading mailbox...
          </div>
        ) : fetchError ? (
          <div className="p-8 text-center text-xs">
            <p className="text-status-warning mb-2">{fetchError}</p>
            <Button size="sm" variant="secondary" onClick={onRetry}>
              Retry Connection
            </Button>
          </div>
        ) : messages.length === 0 ? (
          <div className="p-8 text-center text-xs text-ink-3">
            No messages found in this folder.
          </div>
        ) : (
          messages.map((msg) => (
            <MailMessageRow
              key={msg.id}
              message={msg}
              isSelected={msg.id === selectedMessageId}
              onSelect={onSelectMessage}
            />
          ))
        )}
      </div>
    </div>
  );
}
