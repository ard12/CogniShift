import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { mailApi } from "@/api/mail";

interface MailAiDraftAssistProps {
  onDraftGenerated: (subject: string, body: string) => void;
  onClose: () => void;
}

export function MailAiDraftAssist({
  onDraftGenerated,
  onClose,
}: MailAiDraftAssistProps) {
  const [aiIntent, setAiIntent] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!aiIntent.trim()) return;
    setIsGenerating(true);
    setStatusMessage(null);
    try {
      const draft = await mailApi.draftAssist(aiIntent.trim());
      onDraftGenerated(draft.subject, draft.body);
      setStatusMessage(
        draft.fallback
          ? `Local model unavailable; deterministic fallback used in ${draft.latency_ms}ms`
          : `Draft generated via local ${draft.model} in ${draft.latency_ms}ms`
      );
      setTimeout(() => {
        onClose();
      }, 600);
    } catch (err: unknown) {
      setStatusMessage(
        err instanceof Error ? err.message : "AI drafting failed."
      );
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="rounded-lg border border-brand/40 bg-brand/5 p-3 space-y-2">
      <div className="flex items-center justify-between text-xs font-mono font-bold text-brand">
        <span>Local Operational Draft Assistant</span>
        <button
          type="button"
          onClick={onClose}
          className="text-ink-3 hover:text-ink-1"
        >
          ✕
        </button>
      </div>
      <p className="text-[11px] text-ink-3">
        Describe your operational goal. The configured sovereign local model will generate a structured subject and email body.
      </p>
      <div className="flex gap-2">
        <input
          type="text"
          value={aiIntent}
          onChange={(e) => setAiIntent(e.target.value)}
          placeholder="e.g. Request Zara to approve urgent seal repair on pump P-101A"
          className="flex-1 rounded border border-surface-border bg-surface-1 px-3 py-1.5 text-xs text-ink-1 focus:border-brand focus:outline-none"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void handleGenerate();
            }
          }}
        />
        <Button
          type="button"
          size="sm"
          variant="primary"
          disabled={isGenerating || !aiIntent.trim()}
          onClick={handleGenerate}
        >
          {isGenerating ? "Drafting..." : "Generate"}
        </Button>
      </div>
      {statusMessage && (
        <p
          className={`font-mono text-[10px] ${
            statusMessage.includes("fallback")
              ? "text-status-warning"
              : "text-emerald-400"
          }`}
        >
          {statusMessage}
        </p>
      )}
    </div>
  );
}
