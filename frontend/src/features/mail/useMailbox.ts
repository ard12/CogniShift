import { useCallback, useEffect, useState } from "react";
import { mailApi } from "@/api/mail";
import { securityApi } from "@/api/security";
import { useAuth } from "@/auth/useAuth";
import { useMailEvents } from "./useMailEvents";
import type {
  FolderType,
  MailMessageMetadata,
  MailMessageDetail,
  SmtpHealthStatus,
} from "./types";

export function useMailbox() {
  const { role } = useAuth();
  const [messages, setMessages] = useState<MailMessageMetadata[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [currentUserId, setCurrentUserId] = useState<string>("");
  const [selectedFolder, setSelectedFolder] = useState<FolderType>("all");
  const [filterUnreadOnly, setFilterUnreadOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [selectedMessageId, setSelectedMessageId] = useState<number | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<MailMessageDetail | null>(null);
  const [bodyViewMode, setBodyViewMode] = useState<"html" | "text">("html");

  const [smtpHealth, setSmtpHealth] = useState<SmtpHealthStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isDispatching, setIsDispatching] = useState<boolean>(false);

  const fetchMail = useCallback(async () => {
    try {
      const folderParam = selectedFolder === "all" ? undefined : selectedFolder;
      try {
        const res = await mailApi.list(folderParam, 100, 0);
        setMessages(res.messages);
        setUnreadCount(res.unread_count);
        setTotalCount(res.total_count);
        setCurrentUserId(res.user_id);
        setFetchError(null);
      } catch (err) {
        if (role === "administrator") {
          console.warn("mailApi.list failed, falling back to securityApi.mailbox:", err);
          const mb = await securityApi.mailbox(100, 0);
          setMessages(mb.alerts as unknown as MailMessageMetadata[]);
          setUnreadCount(mb.unread_count);
          setTotalCount(mb.total_count);
          setFetchError(null);
        } else {
          throw err;
        }
      }
      try {
        setSmtpHealth(await mailApi.smtpHealth());
      } catch {
        if (role === "administrator") {
          try {
            setSmtpHealth(await securityApi.smtpHealth());
          } catch {
            // Ignore SMTP health poll fail
          }
        }
      }
    } catch (err) {
      console.error("Mailbox fetch failed:", err);
      setFetchError(err instanceof Error ? err.message : "Mailbox unavailable");
    } finally {
      setIsLoading(false);
    }
  }, [selectedFolder, role]);

  // Initial fetch and 3-second polling fallback
  useEffect(() => {
    void fetchMail();
    const interval = setInterval(() => {
      void fetchMail();
    }, 3000);
    return () => clearInterval(interval);
  }, [fetchMail]);

  // Real-time SSE streaming connection
  useMailEvents({
    onNewMail: fetchMail,
    enabled: true,
  });

  const selectMessage = async (msgId: number) => {
    setSelectedMessageId(msgId);
    try {
      let detail: MailMessageDetail;
      try {
        detail = await mailApi.get(msgId);
      } catch {
        const secDetail = await securityApi.alertDetail(msgId);
        detail = secDetail as unknown as MailMessageDetail;
      }
      setSelectedDetail(detail);

      if (!detail.is_read) {
        try {
          await mailApi.markRead(msgId);
        } catch {
          await securityApi.markAlertRead(msgId);
        }
        setMessages((prev) =>
          prev.map((m) => (m.id === msgId ? { ...m, is_read: 1 } : m))
        );
        setUnreadCount((c) => Math.max(0, c - 1));
      }
    } catch (err) {
      console.error("Failed to load message detail:", err);
    }
  };

  const dispatchTestAlert = async () => {
    setIsDispatching(true);
    try {
      try {
        await mailApi.dispatchTest();
      } catch {
        await securityApi.dispatchTestAlert();
      }
      await fetchMail();
    } catch (err) {
      console.error("Test alert failed:", err);
    } finally {
      setIsDispatching(false);
    }
  };

  const clearMailbox = async () => {
    if (!window.confirm("Purge all messages in internal mailbox (Admin only)?")) return;
    try {
      try {
        await mailApi.clear();
      } catch {
        await securityApi.clearMailbox();
      }
      setSelectedMessageId(null);
      setSelectedDetail(null);
      await fetchMail();
    } catch (err) {
      console.error("Clear mailbox failed:", err);
    }
  };

  const filteredMessages = messages.filter((m) => {
    if (filterUnreadOnly && m.is_read) return false;
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      m.subject.toLowerCase().includes(q) ||
      m.sender.toLowerCase().includes(q) ||
      m.alert_type.toLowerCase().includes(q) ||
      (m.related_user && m.related_user.toLowerCase().includes(q))
    );
  });

  return {
    messages,
    filteredMessages,
    unreadCount,
    totalCount,
    currentUserId,
    selectedFolder,
    setSelectedFolder,
    filterUnreadOnly,
    setFilterUnreadOnly,
    searchQuery,
    setSearchQuery,
    selectedMessageId,
    setSelectedMessageId,
    selectedDetail,
    setSelectedDetail,
    bodyViewMode,
    setBodyViewMode,
    smtpHealth,
    isLoading,
    fetchError,
    isDispatching,
    fetchMail,
    selectMessage,
    dispatchTestAlert,
    clearMailbox,
    role,
  };
}
