import { useEffect, useState } from "react";
import { approvalsApi } from "@/api/approvals";
import { ApprovalCard } from "@/components/ApprovalCard";
import { Button } from "@/components/ui/Button";
import { IconRefresh, IconShieldCheck } from "@/components/ui/Icon";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import type { Approval } from "@/types";

export function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await approvalsApi.listPending();
      setApprovals(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load approvals.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Shift Supervisor Authorization"
        description="High-risk tool calls are paused here for human review before the originating run may resume. Approving or rejecting a request also resumes the associated run automatically."
        actions={
          <Button variant="secondary" size="sm" onClick={() => void load()}>
            <IconRefresh className="h-3.5 w-3.5" /> Refresh
          </Button>
        }
      />

      <Panel>
        <PanelHeader
          icon={<IconShieldCheck className="h-3.5 w-3.5" />}
          title="Pending Requests"
          meta={<span className="font-mono text-[10px] text-ink-3">{approvals.length}</span>}
        />
        <PanelBody>
          {loading ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message={error} />
          ) : approvals.length === 0 ? (
            <EmptyState
              icon={<IconShieldCheck className="h-6 w-6" />}
              title="All safety interlocks nominal"
              description="Zero high-risk interventions gated. Approved and rejected requests are not retained in a separate history by the backend."
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {approvals.map((approval) => (
                <ApprovalCard key={approval.id} approval={approval} onResolved={load} />
              ))}
            </div>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}