import { Link } from "react-router-dom";

export function LandingFooter() {
  return (
    <footer className="border-t border-surface-border bg-surface-1 py-12 px-4 sm:px-8 text-xs font-mono text-ink-3">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <span className="text-lg text-brand" aria-hidden="true">
            ⬡
          </span>
          <div>
            <span className="font-bold text-ink-1 tracking-wider">COGNISHIFT</span>
            <p className="text-[11px] text-ink-3">
              Sovereign On-Premise Agentic AI Workbench (SIH26117)
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-6 text-[11px]">
          <Link to="/app/operator" className="hover:text-brand transition">
            Operator Console
          </Link>
          <Link to="/app/mailbox" className="hover:text-brand transition">
            Operations Mail
          </Link>
          <Link to="/app/knowledge" className="hover:text-brand transition">
            Knowledge Vault
          </Link>
          <Link to="/app/security" className="hover:text-brand transition">
            Sovereign Security
          </Link>
        </div>

        <div className="text-[10px] text-center sm:text-right">
          <div>Purdue Model Level 3/3.5 Architecture</div>
          <div className="text-emerald-400">Zero Cloud Egress Guaranteed</div>
        </div>
      </div>
    </footer>
  );
}
