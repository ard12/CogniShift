import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";

export function WorkbenchTransition() {
  return (
    <section className="py-24 px-4 sm:px-8 text-center relative overflow-hidden">
      {/* Background schematic grid with subtle radial gradient */}
      <div className="absolute inset-0 schematic-grid opacity-20 pointer-events-none" />
      <div className="absolute inset-0 bg-radial from-brand/5 to-transparent pointer-events-none" />

      <div className="relative z-10 max-w-3xl mx-auto space-y-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-brand/40 bg-brand/10 px-3 py-0.5 text-xs font-mono text-brand">
          <span>OPERATIONAL DEPLOYMENT READY</span>
        </div>

        <h2 className="text-3xl sm:text-5xl font-extrabold text-ink-1">
          Zero Cloud Egress. <br />
          <span className="text-brand">100% Sovereign Execution.</span>
        </h2>

        <p className="text-sm sm:text-base text-ink-2 max-w-xl mx-auto leading-relaxed">
          Step into the operator cockpit. Run multi-turn process diagnostics, inspect CAD blueprints, and dispatch safe interventions on on-premise hardware.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
          <Link to="/app/operator">
            <Button size="lg" variant="primary" className="font-mono text-sm font-bold px-8 py-3">
              Enter Sovereign Workbench →
            </Button>
          </Link>
          <Link to="/app/mailbox">
            <Button size="lg" variant="secondary" className="font-mono text-sm px-6 py-3">
              Open Operations Mailbox
            </Button>
          </Link>
        </div>

        <div className="pt-8 flex flex-wrap items-center justify-center gap-6 font-mono text-xs text-ink-3">
          <span>FastAPI 0.115</span>
          <span>·</span>
          <span>Ollama Qwen2.5</span>
          <span>·</span>
          <span>ChromaDB</span>
          <span>·</span>
          <span>FastEmbed</span>
          <span>·</span>
          <span>SQLite WAL</span>
        </div>
      </div>
    </section>
  );
}
