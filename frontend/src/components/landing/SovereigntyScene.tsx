import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { IconLock } from "@/components/ui/Icon";

export function SovereigntyScene() {
  const [testState, setTestState] = useState<"idle" | "intercepted">("idle");

  const runEgressTest = () => {
    setTestState("intercepted");
  };

  return (
    <section id="sovereignty" className="py-20 px-4 sm:px-8 max-w-6xl mx-auto border-b border-surface-border">
      <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-0.5 text-xs font-mono text-emerald-400">
          <IconLock className="h-3.5 w-3.5" />
          <span>PURDUE MODEL LEVEL 3 / 3.5 AIR-GAP</span>
        </div>
        <h2 className="text-2xl sm:text-4xl font-bold text-ink-1">
          Cryptographically Enforced Network Sovereignty
        </h2>
        <p className="text-xs sm:text-sm text-ink-2 leading-relaxed">
          In high-hazard PSU, defense, and refinery environments, data leakage is an existential safety and national security risk.
          CogniShift enforces zero cloud egress at both software and container boundary layers.
        </p>
      </div>

      {/* Network Topology Schematic */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
        {/* Exterior: Public Cloud (Blocked) */}
        <div className="rounded-xl border border-surface-border bg-surface-2/40 p-5 flex flex-col justify-between opacity-80">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-xs font-bold text-status-error uppercase tracking-wider">
                EXTERIOR / PUBLIC CLOUD
              </span>
              <span className="rounded bg-status-error/15 px-2 py-0.5 font-mono text-[9px] font-bold text-status-error border border-status-error/30">
                BLOCKED (0 B/s)
              </span>
            </div>
            <p className="text-xs text-ink-3 leading-relaxed mb-4">
              All remote APIs, external inference providers (OpenAI, Anthropic, Gemini), and cloud metric exporters are strictly prohibited.
            </p>
            <div className="space-y-2 font-mono text-xs text-ink-3">
              <div className="flex items-center justify-between rounded border border-surface-border bg-surface-1 p-2">
                <span>api.openai.com</span>
                <span className="text-status-error">CONNECTION REFUSED</span>
              </div>
              <div className="flex items-center justify-between rounded border border-surface-border bg-surface-1 p-2">
                <span>huggingface.co</span>
                <span className="text-status-error">FAIL CLOSED</span>
              </div>
              <div className="flex items-center justify-between rounded border border-surface-border bg-surface-1 p-2">
                <span>telemetry.cloud.io</span>
                <span className="text-status-error">ROUTE NULL</span>
              </div>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-surface-border font-mono text-[10px] text-ink-3 text-center">
            EGRESS ENFORCEMENT: FAIL-CLOSED
          </div>
        </div>

        {/* Center: Industrial DMZ & Loopback Barrier */}
        <div className="rounded-xl border-2 border-brand/50 bg-brand/5 p-5 flex flex-col justify-between shadow-lg relative overflow-hidden">
          <div className="absolute -top-12 -right-12 w-28 h-28 bg-brand/10 rounded-full blur-2xl pointer-events-none" />
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-xs font-bold text-brand uppercase tracking-wider">
                AIR-GAP PERIMETER
              </span>
              <span className="rounded bg-brand/20 px-2 py-0.5 font-mono text-[9px] font-bold text-brand border border-brand/40">
                LOOPBACK ONLY
              </span>
            </div>
            <p className="text-xs text-ink-2 leading-relaxed mb-4">
              All system communications terminate on loopback (127.0.0.1) or strictly bounded industrial subnet.
              Isolated Docker sandbox executes code with no net host access.
            </p>
            <div className="space-y-2 font-mono text-xs">
              <div className="rounded border border-brand/30 bg-surface-1 p-2 text-ink-1">
                <span className="text-brand font-bold">127.0.0.1:8000</span> — FastAPI REST &amp; SSE
              </div>
              <div className="rounded border border-brand/30 bg-surface-1 p-2 text-ink-1">
                <span className="text-brand font-bold">127.0.0.1:8025</span> — SMTP Loopback Mail
              </div>
              <div className="rounded border border-brand/30 bg-surface-1 p-2 text-ink-1">
                <span className="text-brand font-bold">127.0.0.1:11434</span> — Ollama Local GPU Engine
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-brand/20">
            <Button
              size="sm"
              variant="primary"
              className="w-full font-mono text-xs"
              onClick={runEgressTest}
            >
              Verify Network Air-Gap →
            </Button>
            {testState === "intercepted" && (
              <div className="mt-2 rounded bg-emerald-500/10 border border-emerald-500/30 p-2 font-mono text-[10px] text-emerald-400 text-center">
                ✓ SIMULATED EGRESS ATTEMPT INTERCEPTED &amp; DROPPED (0 BYTES LEAKED)
              </div>
            )}
          </div>
        </div>

        {/* Interior: Sovereign Local Compute */}
        <div className="rounded-xl border border-surface-border bg-surface-2/40 p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-xs font-bold text-emerald-400 uppercase tracking-wider">
                SOVEREIGN LOCAL COMPUTE
              </span>
              <span className="rounded bg-emerald-500/15 px-2 py-0.5 font-mono text-[9px] font-bold text-emerald-400 border border-emerald-500/30">
                ON-PREMISE
              </span>
            </div>
            <p className="text-xs text-ink-3 leading-relaxed mb-4">
              Local workstation hardware powers the entire stack: embedding inference, visual vector search, and LLM reasoning.
            </p>
            <div className="space-y-2 font-mono text-xs text-ink-2">
              <div className="flex items-center justify-between rounded border border-surface-border bg-surface-1 p-2">
                <span>NVIDIA RTX 3050</span>
                <span className="text-emerald-400">VRAM: 4.2 GB OFF</span>
              </div>
              <div className="flex items-center justify-between rounded border border-surface-border bg-surface-1 p-2">
                <span>ChromaDB Vector Store</span>
                <span className="text-emerald-400">LOCAL EMBEDDINGS</span>
              </div>
              <div className="flex items-center justify-between rounded border border-surface-border bg-surface-1 p-2">
                <span>SQLite WAL DB</span>
                <span className="text-emerald-400">ACID TRANSACTIONS</span>
              </div>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-surface-border font-mono text-[10px] text-ink-3 text-center">
            ZERO TELEMETRY EGRESS VERIFIED
          </div>
        </div>
      </div>
    </section>
  );
}
