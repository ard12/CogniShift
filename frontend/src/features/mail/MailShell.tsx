import { useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { IconMail, IconRefresh, IconTrash } from "@/components/ui/Icon";
import { useWorkspaces } from "@/context/useWorkspaces";
import { useMailbox } from "./useMailbox";
import { MailSidebar } from "./MailSidebar";
import { MailMessageList } from "./MailMessageList";
import { MailMessageDetail } from "./MailMessageDetail";
import { MailCompose } from "./MailCompose";
import { PermitRequestModal } from "./PermitRequestModal";
import type { FolderType } from "./types";

export function MailShell() {
  const { selectedWorkspaceId } = useWorkspaces();
  const mailbox = useMailbox();
  const [showComposeModal, setShowComposeModal] = useState(false);
  const [showRequestModal, setShowRequestModal] = useState(false);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] p-4 gap-3">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <PageHeader
          title="Sovereign Industrial Mailbox"
          description={`Internal Messaging · Role: ${mailbox.role ?? "operator"}`}
        />
        <div className="flex items-center gap-2">
          {mailbox.smtpHealth && (
            <div
              className={`flex items-center gap-1.5 rounded border px-2.5 py-1 text-[11px] font-mono ${
                mailbox.smtpHealth.status === "ACTIVE"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                  : "border-status-error/40 bg-status-error/10 text-status-error"
              }`}
              title={mailbox.smtpHealth.banner || mailbox.smtpHealth.error}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  mailbox.smtpHealth.status === "ACTIVE"
                    ? "bg-emerald-400 animate-pulse"
                    : "bg-status-error"
                }`}
              />
              <span>
                SMTP {mailbox.smtpHealth.host}:{mailbox.smtpHealth.port}
              </span>
            </div>
          )}

          <Button
            size="sm"
            variant="primary"
            onClick={() => setShowComposeModal(true)}
            className="bg-brand text-black font-semibold hover:bg-brand/90"
          >
            <IconMail className="h-3.5 w-3.5 mr-1" />
            Compose
          </Button>

          <Button
            size="sm"
            variant="secondary"
            onClick={() => setShowRequestModal(true)}
          >
            + Request Permit
          </Button>

          {(mailbox.role === "supervisor" || mailbox.role === "administrator") && (
            <Button
              size="sm"
              variant="secondary"
              disabled={mailbox.isDispatching}
              onClick={() => void mailbox.dispatchTestAlert()}
              className="hidden sm:inline-flex"
            >
              {mailbox.isDispatching ? "Dispatching..." : "Test Alert"}
            </Button>
          )}

          {mailbox.role === "administrator" && mailbox.messages.length > 0 && (
            <Button
              size="sm"
              variant="secondary"
              className="border-status-error/40 text-status-error hover:bg-status-error/10 hidden sm:inline-flex"
              onClick={() => void mailbox.clearMailbox()}
            >
              <IconTrash className="h-3.5 w-3.5 mr-1" />
              Clear
            </Button>
          )}

          <Button
            size="sm"
            variant="secondary"
            onClick={() => void mailbox.fetchMail()}
            title="Refresh mailbox"
          >
            <IconRefresh className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Mobile folder selector pills */}
      <div className="flex md:hidden items-center gap-1 overflow-x-auto pb-1 text-xs shrink-0">
        {[
          { key: "all", label: "Inbound" },
          { key: "sent", label: "Sent" },
          { key: "permits", label: "Permits" },
          { key: "security", label: "Security" },
          { key: "governance", label: "Governance" },
        ].map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => {
              mailbox.setSelectedFolder(f.key as FolderType);
              mailbox.setSelectedMessageId(null);
            }}
            className={`whitespace-nowrap px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
              mailbox.selectedFolder === f.key
                ? "bg-brand text-black border-brand font-bold"
                : "bg-surface-2 text-ink-2 border-surface-border"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* 3-PANE EMAIL CLIENT LAYOUT */}
      <div className="flex flex-1 min-h-0 rounded-xl border border-surface-border bg-surface-1 overflow-hidden shadow-2xl">
        {/* Pane 1: Sidebar */}
        <MailSidebar
          selectedFolder={mailbox.selectedFolder}
          onSelectFolder={(f) => {
            mailbox.setSelectedFolder(f);
            mailbox.setSelectedMessageId(null);
          }}
          unreadCount={mailbox.unreadCount}
          totalCount={mailbox.totalCount}
          filterUnreadOnly={mailbox.filterUnreadOnly}
          onToggleUnreadOnly={() => mailbox.setFilterUnreadOnly(!mailbox.filterUnreadOnly)}
          smtpHealth={mailbox.smtpHealth}
        />

        {/* Pane 2: Message List */}
        <MailMessageList
          messages={mailbox.filteredMessages}
          selectedMessageId={mailbox.selectedMessageId}
          onSelectMessage={(id) => void mailbox.selectMessage(id)}
          searchQuery={mailbox.searchQuery}
          onSearchChange={mailbox.setSearchQuery}
          isLoading={mailbox.isLoading}
          fetchError={mailbox.fetchError}
          onRetry={() => void mailbox.fetchMail()}
        />

        {/* Pane 3: Message Detail */}
        <MailMessageDetail
          detail={mailbox.selectedDetail}
          role={mailbox.role}
          workspaceId={selectedWorkspaceId}
          bodyViewMode={mailbox.bodyViewMode}
          onToggleBodyViewMode={mailbox.setBodyViewMode}
          onBackMobile={() => {
            mailbox.setSelectedMessageId(null);
            mailbox.setSelectedDetail(null);
          }}
          onDetailUpdated={() => {
            if (mailbox.selectedDetail) {
              void mailbox.selectMessage(mailbox.selectedDetail.id);
            }
            void mailbox.fetchMail();
          }}
        />
      </div>

      {/* Compose Modal */}
      <MailCompose
        isOpen={showComposeModal}
        onClose={() => setShowComposeModal(false)}
        currentUserId={mailbox.currentUserId}
        onMailSent={async (alertId) => {
          mailbox.setSelectedFolder("sent");
          await mailbox.fetchMail();
          if (alertId) {
            await mailbox.selectMessage(alertId);
          }
        }}
      />

      {/* Request Permit Modal */}
      <PermitRequestModal
        isOpen={showRequestModal}
        onClose={() => setShowRequestModal(false)}
        workspaceId={selectedWorkspaceId}
        onPermitRequested={() => void mailbox.fetchMail()}
      />
    </div>
  );
}
