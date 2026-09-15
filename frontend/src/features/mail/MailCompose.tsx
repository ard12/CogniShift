import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { IconMail } from "@/components/ui/Icon";
import { mailApi } from "@/api/mail";
import { MailAiDraftAssist } from "./MailAiDraftAssist";
import type { MailAttachment, MailRecipient } from "./types";

interface MailComposeProps {
  isOpen: boolean;
  onClose: () => void;
  currentUserId: string;
  onMailSent: (alertId?: number) => void;
}

export function MailCompose({
  isOpen,
  onClose,
  currentUserId,
  onMailSent,
}: MailComposeProps) {
  const [availableRecipients, setAvailableRecipients] = useState<MailRecipient[]>([]);
  const [selectedRecipients, setSelectedRecipients] = useState<string[]>([]);
  const [recipientFilter, setRecipientFilter] = useState("");
  const [composeSubject, setComposeSubject] = useState("");
  const [composeBody, setComposeBody] = useState("");
  const [composeAttachments, setComposeAttachments] = useState<MailAttachment[]>([]);
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [isSendingMail, setIsSendingMail] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [showAiAssist, setShowAiAssist] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setSendError(null);
    setAttachmentError(null);
    mailApi
      .recipients()
      .then(setAvailableRecipients)
      .catch((err) => console.error("Failed to load recipients:", err));
  }, [isOpen]);

  if (!isOpen) return null;

  const toggleRecipient = (userId: string) => {
    setSelectedRecipients((prev) =>
      prev.includes(userId) ? prev.filter((u) => u !== userId) : [...prev, userId]
    );
  };

  const handleAttachmentUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];

    const allowed = [".pdf", ".docx", ".xlsx", ".csv", ".txt", ".png", ".jpg", ".jpeg"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!allowed.includes(ext)) {
      setAttachmentError(`File extension '${ext}' is not permitted. Allowed: ${allowed.join(", ")}`);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setAttachmentError("File size exceeds 10 MB limit.");
      return;
    }

    setIsUploadingAttachment(true);
    setAttachmentError(null);

    try {
      const uploaded = await mailApi.uploadAttachment(file);
      setComposeAttachments((prev) => [
        ...prev,
        {
          id: uploaded.id,
          filename: uploaded.filename,
          file_size: uploaded.file_size,
          content_type: uploaded.content_type,
          sha256_hash: uploaded.sha256,
        },
      ]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err: unknown) {
      setAttachmentError(err instanceof Error ? err.message : "Failed to upload attachment.");
    } finally {
      setIsUploadingAttachment(false);
    }
  };

  const removeAttachment = (attId: number) => {
    setComposeAttachments((prev) => prev.filter((a) => a.id !== attId));
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedRecipients.length === 0) {
      setSendError("Please select at least one recipient.");
      return;
    }
    if (!composeSubject.trim()) {
      setSendError("Please enter a subject.");
      return;
    }
    if (!composeBody.trim()) {
      setSendError("Please enter a message body.");
      return;
    }

    setIsSendingMail(true);
    setSendError(null);

    try {
      const res = await mailApi.send({
        recipients: selectedRecipients,
        subject: composeSubject.trim(),
        body_text: composeBody.trim(),
        attachment_ids: composeAttachments.map((a) => a.id),
      });

      setSelectedRecipients([]);
      setComposeSubject("");
      setComposeBody("");
      setComposeAttachments([]);
      onClose();
      onMailSent(res.alert_id);
    } catch (err: unknown) {
      setSendError(err instanceof Error ? err.message : "Failed to send message.");
    } finally {
      setIsSendingMail(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-3 md:p-4 backdrop-blur-sm">
      <form
        onSubmit={handleSend}
        className="w-full max-w-2xl rounded-xl border border-surface-border bg-surface-1 p-5 space-y-4 shadow-2xl max-h-[92vh] flex flex-col"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-surface-border pb-3 shrink-0">
          <div className="flex items-center gap-2">
            <IconMail className="h-4 w-4 text-brand" />
            <h3 className="font-bold text-base text-ink-1">Compose Internal Message</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-ink-3 hover:text-ink-1 text-sm font-bold p-1"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3 text-xs overflow-y-auto pr-1 flex-1">
          {/* Recipients Selection */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-ink-3 font-mono font-medium">
                Recipients (Select team members)
              </label>
              <input
                type="text"
                placeholder="Filter names..."
                value={recipientFilter}
                onChange={(e) => setRecipientFilter(e.target.value)}
                className="rounded border border-surface-border bg-surface-2 px-2 py-0.5 text-[11px] text-ink-1 focus:border-brand focus:outline-none"
              />
            </div>
            <div className="flex flex-wrap gap-1.5 p-2 rounded border border-surface-border bg-surface-2 min-h-[38px] max-h-28 overflow-y-auto">
              {availableRecipients.length === 0 ? (
                <span className="text-ink-3 text-xs">Loading team directory...</span>
              ) : (
                availableRecipients
                  .filter(
                    (r) =>
                      !recipientFilter.trim() ||
                      r.display_name.toLowerCase().includes(recipientFilter.toLowerCase()) ||
                      r.role.toLowerCase().includes(recipientFilter.toLowerCase()) ||
                      r.user_id.toLowerCase().includes(recipientFilter.toLowerCase())
                  )
                  .map((rec) => {
                    const isSelected = selectedRecipients.includes(rec.user_id);
                    return (
                      <button
                        key={rec.user_id}
                        type="button"
                        onClick={() => toggleRecipient(rec.user_id)}
                        className={`rounded-full px-2.5 py-1 text-xs font-mono transition-colors flex items-center gap-1.5 border ${
                          isSelected
                            ? "bg-brand text-black border-brand font-bold shadow-sm"
                            : "bg-surface-1 text-ink-2 border-surface-border hover:border-ink-3"
                        }`}
                      >
                        <span>{rec.display_name}</span>
                        <span
                          className={`text-[10px] opacity-75 ${
                            isSelected ? "text-black" : "text-ink-3"
                          }`}
                        >
                          ({rec.role})
                        </span>
                      </button>
                    );
                  })
              )}
            </div>
            {selectedRecipients.length > 0 && (
              <p className="font-mono text-[10px] text-ink-3 mt-1">
                Selected ({selectedRecipients.length}): {selectedRecipients.join(", ")}
              </p>
            )}
          </div>

          {/* Subject + AI Assist Trigger */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-ink-3 font-mono font-medium">Subject</label>
              <button
                type="button"
                onClick={() => setShowAiAssist((v) => !v)}
                className="text-brand hover:underline font-mono text-[11px] flex items-center gap-1 font-semibold"
              >
                <span>✨ Improve with Local AI</span>
              </button>
            </div>
            <input
              type="text"
              value={composeSubject}
              onChange={(e) => setComposeSubject(e.target.value)}
              placeholder="e.g. Unit 4 Scheduled Inspection & Maintenance Handoff"
              className="w-full rounded border border-surface-border bg-surface-2 px-3 py-1.5 text-xs text-ink-1 font-medium focus:border-brand focus:outline-none"
              required
            />
          </div>

          {/* Local AI Assistant Box */}
          {showAiAssist && (
            <MailAiDraftAssist
              onDraftGenerated={(subj, body) => {
                setComposeSubject(subj);
                setComposeBody(body);
              }}
              onClose={() => setShowAiAssist(false)}
            />
          )}

          {/* Message Body */}
          <div>
            <label className="block text-ink-3 font-mono mb-1 font-medium">
              Message Body
            </label>
            <textarea
              rows={6}
              value={composeBody}
              onChange={(e) => setComposeBody(e.target.value)}
              placeholder="Enter clear, professional operational communications..."
              className="w-full rounded border border-surface-border bg-surface-2 px-3 py-2 text-xs text-ink-1 font-sans leading-relaxed focus:border-brand focus:outline-none resize-none"
              required
            />
          </div>

          {/* Attachments Upload & Chips */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-ink-3 font-mono font-medium">
                Attachments (Max 10MB: .pdf, .docx, .xlsx, .csv, .txt, .png, .jpg)
              </label>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploadingAttachment}
                className="text-brand hover:underline font-mono text-[11px] font-semibold"
              >
                {isUploadingAttachment ? "Uploading..." : "+ Add File"}
              </button>
            </div>

            <input
              type="file"
              ref={fileInputRef}
              onChange={handleAttachmentUpload}
              className="hidden"
              accept=".pdf,.docx,.xlsx,.csv,.txt,.png,.jpg,.jpeg"
            />

            {composeAttachments.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {composeAttachments.map((att) => (
                  <div
                    key={att.id}
                    className="flex items-center gap-2 rounded-lg border border-surface-border bg-surface-2 px-2.5 py-1 text-xs font-mono"
                  >
                    <span className="text-ink-1 font-medium truncate max-w-[180px]">
                      {att.filename}
                    </span>
                    <span className="text-ink-3 text-[10px]">
                      ({(att.file_size / 1024).toFixed(1)} KB)
                    </span>
                    <button
                      type="button"
                      onClick={() => removeAttachment(att.id)}
                      className="text-status-error hover:text-status-error/80 font-bold ml-1"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}

            {attachmentError && (
              <p className="font-mono text-[10px] text-status-error mt-1">
                {attachmentError}
              </p>
            )}
          </div>

          {sendError && (
            <div className="rounded border border-status-error/40 bg-status-error/10 p-2 text-xs font-mono text-status-error">
              {sendError}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-surface-border shrink-0">
          <span className="font-mono text-[10px] text-ink-3">
            Sender: <strong>{currentUserId || "not-verified"}@secure.internal</strong>
          </span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
              disabled={isSendingMail}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={isSendingMail || selectedRecipients.length === 0}
              className="bg-brand text-black font-semibold"
            >
              {isSendingMail ? "Sending..." : "Send Message"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
