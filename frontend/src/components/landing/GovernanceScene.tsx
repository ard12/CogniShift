import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { IconCheck, IconLock, IconShieldCheck } from "@/components/ui/Icon";

export function GovernanceScene() {
  const [approvalsCount, setApprovalsCount] = useState(0);
  const [isConsumed, setIsConsumed] = useState(false);

  const handleApprove = () => {
    if (approvalsCount === 0) setApprovalsCount(1);
    else if (approvalsCount === 1) setApprovalsCount(2);
  };

  const handleExecute = () => {
    setIsConsumed(true);
  };

  const handleReset = () => {
    setApprovalsCount(0);
    setIsConsumed(false);
  };

  return (
    <section id="governance" className="py-20 px-4 sm:px-8 max-w-6xl mx-auto border-b border-surface-border">
      <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-brand/40 bg-brand/10 px-3 py-0.5 text-xs font-mono text-brand">
          <IconLock className="h-3.5 w-3.5" />
          <span>FOUR-EYES SAFETY INTERLOCK</span>
        </div>
        <h2 className="text-2xl sm:text-4xl font-bold text-ink-1">
          Dual-Supervisor Governance &amp; Single-Use Permits
        </h2>
        <p className="text-xs sm:text-sm text-ink-2 leading-relaxed">
          Autonomous AI agents must never be permitted to actuate high-hazard refinery valves, breakers, or trips unsupervised.
          CogniShift halts all destructive actions until two independent human supervisors grant dual authorization.
        </p>
      </div>

      <div className="rounded-xl border border-surface-border bg-surface-2/60 p-6 shadow-xl max-w-4xl mx-auto">
        <div className="flex flex-wrap items-center justify-between border-b border-surface-border pb-4 gap-2">
          <div className="flex items-center gap-2 font-mono text-xs text-ink-1">
            <IconShieldCheck className="h-4 w-4 text-brand" />
            <span className="font-bold">PROPOSED ACTION:</span>
            <code className="rounded bg-surface-3 px-2 py-0.5 text-brand">
              operate_pump [P-101A] --mode restart
            </code>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs">
            <span className="text-ink-3">PERMIT STATUS:</span>
            <span
              className={`rounded px-2.5 py-0.5 font-bold ${
                isConsumed
                  ? "bg-surface-3 text-ink-3 border border-surface-border"
                  : approvalsCount === 2
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                  : "bg-status-warning/20 text-status-warning border border-status-warning/40"
              }`}
            >
              {isConsumed
                ? "CONSUMED (0/1 USES)"
                : approvalsCount === 2
                ? "ACTIVE (1/1 READY)"
                : `PENDING (${approvalsCount}/2 APPROVALS)`}
            </span>
          </div>
        </div>

        {/* 2-Step Signer Visualization */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-6">
          {/* Signer 1 */}
          <div
            className={`rounded-lg border p-4 transition-all ${
              approvalsCount >= 1
                ? "border-emerald-500/40 bg-emerald-500/5"
                : "border-surface-border bg-surface-1"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-xs font-bold text-ink-1">
                Supervisor 1: Zara (Shift Lead)
              </span>
              {approvalsCount >= 1 ? (
                <span className="flex items-center gap-1 font-mono text-[10px] text-emerald-400 font-bold">
                  <IconCheck className="h-3.5 w-3.5" /> SIGNED
                </span>
              ) : (
                <span className="font-mono text-[10px] text-ink-3">AWAITING SIGNATURE</span>
              )}
            </div>
            <p className="text-xs text-ink-3 font-mono">
              Role: Operations Shift Supervisor · Device: 10.10.1.14
            </p>
            {approvalsCount >= 1 && (
              <p className="mt-2 font-mono text-[10px] text-emerald-300">
                Timestamp: 02:51:04 IST · Token: RSA-2048-SIG-OK
              </p>
            )}
          </div>

          {/* Signer 2 */}
          <div
            className={`rounded-lg border p-4 transition-all ${
              approvalsCount >= 2
                ? "border-emerald-500/40 bg-emerald-500/5"
                : "border-surface-border bg-surface-1"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-xs font-bold text-ink-1">
                Supervisor 2: Rakshita (Safety Officer)
              </span>
              {approvalsCount >= 2 ? (
                <span className="flex items-center gap-1 font-mono text-[10px] text-emerald-400 font-bold">
                  <IconCheck className="h-3.5 w-3.5" /> SIGNED
                </span>
              ) : (
                <span className="font-mono text-[10px] text-ink-3">AWAITING SIGNATURE</span>
              )}
            </div>
            <p className="text-xs text-ink-3 font-mono">
              Role: Plant Safety Superintendent · Device: 10.10.1.18
            </p>
            {approvalsCount >= 2 && (
              <p className="mt-2 font-mono text-[10px] text-emerald-300">
                Timestamp: 02:51:38 IST · Token: RSA-2048-SIG-OK
              </p>
            )}
          </div>
        </div>

        {/* Interactive Controls */}
        <div className="flex flex-wrap items-center justify-between pt-4 border-t border-surface-border gap-3">
          <div className="text-xs font-mono text-ink-3">
            {!isConsumed && approvalsCount < 2 && "Requires 2 distinct authenticated supervisor approvals."}
            {!isConsumed && approvalsCount === 2 && "Consensus reached. Single-use permit token is armed."}
            {isConsumed && "One-time token consumed. Re-execution attempts fail closed."}
          </div>

          <div className="flex items-center gap-2">
            {approvalsCount < 2 && (
              <Button size="sm" variant="primary" onClick={handleApprove}>
                {approvalsCount === 0 ? "Approve as Supervisor 1 →" : "Approve as Supervisor 2 →"}
              </Button>
            )}

            {approvalsCount === 2 && !isConsumed && (
              <Button size="sm" variant="success" onClick={handleExecute}>
                Execute &amp; Consume Single-Use Permit
              </Button>
            )}

            {(approvalsCount > 0 || isConsumed) && (
              <Button size="sm" variant="secondary" onClick={handleReset}>
                Reset Demo State
              </Button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
