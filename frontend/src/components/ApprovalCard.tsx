import { useState } from "react";
import { approvalsApi } from "@/api/approvals";
import { ApiError } from "@/api/clients";
import { formatRelativeTime, prettyJson, riskLevelTone } from "@/lib/format";
import type { Approval } from "@/types";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { IconAlertTriangle, IconCheck, IconX } from "./ui/Icon";
import { InlineError } from "./ui/States";

export function ApprovalCard({
  approval,
  onResolved,
}: {
  approval: Approval;
  onResolved: () => void;
}) {
  const [pending, setPending] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handle(action: "approve" | "reject") {
    setPending(action);
    setError(null);
    try {
      if (action === "approve") {
        await approvalsApi.approve(approval.id);
      } else {
        await approvalsApi.reject(approval.id);
      }
      onResolved();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Request failed.");
      }
    } finally {
      setPending(null);
    }
  }

  const params = prettyJson(approval.parameters);

  return (
    <div className="space-y-2 rounded border border-status-warning/40 bg-status-warning/5 p-3 font-mono text-xs">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 font-bold uppercase tracking-wide text-status-warning">
          <IconAlertTriangle className="h-3.5 w-3.5" />
          Interlock #{approval.id}
        </span>
        <Badge tone={riskLevelTone(approval.risk_level)}>{approval.risk_level ?? "unknown"}</Badge>
      </div>

      <p className="font-sans text-[13px] text-ink-1">{approval.request_reason ?? "No reason provided."}</p>

      {params && (
        <pre className="max-h-32 overflow-auto rounded border border-surface-border bg-surface-1 p-2 text-[10px] text-ink-3">
          {params}
        </pre>
      )}

      <div className="flex items-center justify-between text-[10px] text-ink-3">
        <span>Run #{approval.run_id}</span>
        <span>Requested {formatRelativeTime(approval.requested_at)}</span>
      </div>

      {error && <InlineError message={error} />}

      <div className="flex gap-2 pt-1">
        <Button
          variant="success"
          size="sm"
          className="flex-1"
          onClick={() => handle("approve")}
          loading={pending === "approve"}
          disabled={pending !== null}
        >
          <IconCheck className="h-3.5 w-3.5" /> Authorize
        </Button>
        <Button
          variant="danger"
          size="sm"
          className="flex-1"
          onClick={() => handle("reject")}
          loading={pending === "reject"}
          disabled={pending !== null}
        >
          <IconX className="h-3.5 w-3.5" /> Reject
        </Button>
      </div>
    </div>
  );
}