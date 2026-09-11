import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { IconShieldCheck, IconTerminal } from "@/components/ui/Icon";

export function HeroScene() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [rotate, setRotate] = useState({ x: 8, y: -6 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      const { innerWidth, innerHeight } = window;
      const xRatio = (e.clientX / innerWidth - 0.5) * 2;
      const yRatio = (e.clientY / innerHeight - 0.5) * 2;
      setRotate({
        x: 8 - yRatio * 10,
        y: -6 + xRatio * 12,
      });
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  return (
    <section className="relative min-h-[90vh] flex flex-col items-center justify-center overflow-hidden py-16 px-4 sm:px-8 border-b border-surface-border">
      {/* Background schematic grid */}
      <div className="absolute inset-0 schematic-grid opacity-30 pointer-events-none" />

      {/* Hero Header */}
      <div className="relative z-10 max-w-4xl text-center space-y-4 mb-12">
        <div className="inline-flex items-center gap-2 rounded-full border border-brand/40 bg-brand/10 px-3.5 py-1 text-xs font-mono text-brand">
          <IconShieldCheck className="h-4 w-4" />
          <span>OFFLINE INDUSTRIAL INTELLIGENCE · ZERO CLOUD DEPENDENCY</span>
        </div>

        <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-ink-1 font-sans">
          Sovereign Industrial <br />
          <span className="text-brand">AI Engineering Workbench</span>
        </h1>

        <p className="max-w-2xl mx-auto text-sm sm:text-base text-ink-2 leading-relaxed">
          Air-gapped agentic orchestration for high-hazard refineries, power plants, and PSUs.
          Performs multi-modal P&amp;ID visual reasoning, Section 17 Root Cause Analysis, and
          dual-supervisor four-eyes safety interlocks with <strong className="text-ink-1">zero cloud egress</strong>.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link to="/app/operator">
            <Button size="lg" variant="primary" className="font-mono text-xs sm:text-sm font-bold px-6 py-2.5">
              Enter Sovereign Workbench →
            </Button>
          </Link>
          <a href="#sovereignty">
            <Button size="lg" variant="secondary" className="font-mono text-xs sm:text-sm px-5 py-2.5">
              Inspect Air-Gap Proofs
            </Button>
          </a>
        </div>
      </div>

      {/* 3D Perspective Floating Console & Engineering Artifacts */}
      <div
        ref={containerRef}
        className="relative z-10 w-full max-w-5xl h-[420px] sm:h-[480px] perspective-1000 flex items-center justify-center"
      >
        <div
          className="relative w-full h-full preserve-3d transition-transform duration-200 ease-out flex items-center justify-center"
          style={{
            transform: `rotateX(${rotate.x}deg) rotateY(${rotate.y}deg)`,
          }}
        >
          {/* Main Floating Operator Console */}
          <div
            className="absolute z-20 w-[92%] sm:w-[680px] rounded-xl border border-surface-border-strong bg-surface-2/95 shadow-2xl p-4 sm:p-6 backdrop-blur-md"
            style={{ transform: "translateZ(40px)" }}
          >
            {/* Window header */}
            <div className="flex items-center justify-between border-b border-surface-border pb-3 mb-3">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-status-error/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-status-warning/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-status-success/80" />
                <span className="ml-2 font-mono text-[11px] text-ink-3">
                  OPERATOR_CONSOLE // WORKSPACE_01 // ASSET: R-301
                </span>
              </div>
              <span className="rounded bg-brand/15 px-2 py-0.5 font-mono text-[9px] font-bold text-brand uppercase">
                RTX-3050 ACCELERATED
              </span>
            </div>

            {/* Terminal prompt */}
            <div className="rounded-lg border border-surface-border bg-surface-1 p-3 font-mono text-xs text-ink-1 space-y-1.5">
              <div className="flex items-center gap-2 text-ink-3">
                <IconTerminal className="h-3.5 w-3.5 text-brand" />
                <span className="text-brand font-semibold">operator@refinery-core:~$</span>
                <span>cognishift audit --asset P-101A --sensor PT-101</span>
              </div>
              <p className="text-ink-2 text-[11px] leading-relaxed">
                &gt; Pressure transmitter PT-101 reading 495 PSI exceeds design MAWP (450 PSI).
                Cross-verify bypass isolation valve FV-302 and initiate RCA Section 17 protocol.
              </p>
            </div>

            {/* Real-time reasoning telemetry trace */}
            <div className="mt-3 rounded-lg border border-surface-border bg-black/40 p-3 font-mono text-[11px] space-y-1 text-ink-3">
              <div className="flex items-center justify-between text-ink-2">
                <span className="text-brand">⚡ RETRIEVAL &amp; REASONING PIPELINE:</span>
                <span className="text-emerald-400 font-bold">LATENCY: 142ms</span>
              </div>
              <p className="text-ink-2">
                [00.018s] <span className="text-cyan-400">FASTEMBED</span>: 3 chunks retrieved from SOP-EXP-2024.pdf (dist: 0.21)
              </p>
              <p className="text-ink-2">
                [00.046s] <span className="text-indigo-400">COLMODERNVBERT</span>: CAD Blueprint P-ID-04-B matched spatial tag [FV-302]
              </p>
              <p className="text-ink-2">
                [00.089s] <span className="text-emerald-400">TOPOLOGY</span>: Upstream: P-101A | Downstream: Reactor R-301 | Interlock: SV-402
              </p>
              <p className="text-amber-300 font-semibold">
                [00.142s] FOUR-EYES GATE: Emergency pressure relief intervention locked pending dual supervisor sign-off.
              </p>
            </div>
          </div>

          {/* Background Document Card 1: ASME BPVC Excerpt */}
          <div
            className="hidden sm:block absolute -left-6 top-8 w-60 rounded-lg border border-surface-border bg-surface-1/90 p-3 shadow-xl backdrop-blur-sm pointer-events-none"
            style={{ transform: "translateZ(-30px) rotate(-6deg)" }}
          >
            <span className="block font-mono text-[9px] font-bold text-brand uppercase tracking-wider">
              SPECIFICATION ARCHIVE
            </span>
            <p className="font-mono text-[11px] font-semibold text-ink-1 mt-1">
              ASME BPVC SEC. VIII DIV. 1
            </p>
            <div className="mt-2 space-y-1 font-mono text-[9px] text-ink-3">
              <div>MAWP Limit: <span className="text-status-error font-bold">450.0 PSI</span></div>
              <div>Relief Margin: 1.10x Max</div>
              <div>Vessel Tag: R-301 Hydrotreater</div>
            </div>
          </div>

          {/* Background Document Card 2: P&ID Blueprint Excerpt */}
          <div
            className="hidden sm:block absolute -right-6 bottom-6 w-64 rounded-lg border border-surface-border bg-surface-1/90 p-3 shadow-xl backdrop-blur-sm pointer-events-none"
            style={{ transform: "translateZ(-15px) rotate(5deg)" }}
          >
            <span className="block font-mono text-[9px] font-bold text-indigo-400 uppercase tracking-wider">
              CAD SCHEMATIC EVIDENCE
            </span>
            <p className="font-mono text-[11px] font-semibold text-ink-1 mt-1">
              DWG: P-ID-04-B (SHEET 2)
            </p>
            <div className="mt-2 space-y-1 font-mono text-[9px] text-ink-3">
              <div>Valve: <span className="text-brand font-semibold">FV-302 (Normally Closed)</span></div>
              <div>Sensor: <span className="text-ink-1">PT-101 [0-600 PSI]</span></div>
              <div>Grounding: Bounding Box [412, 120, 480, 210]</div>
            </div>
          </div>
        </div>
      </div>

      {/* Sovereign Highlights Strip */}
      <div className="relative z-10 grid grid-cols-2 md:grid-cols-4 gap-3 max-w-5xl w-full mt-8">
        <div className="rounded-lg border border-surface-border bg-surface-2/60 p-3 text-center">
          <span className="block font-mono text-lg font-bold text-brand">100% OFFLINE</span>
          <span className="font-mono text-[10px] text-ink-3 uppercase">Zero Cloud API Calls</span>
        </div>
        <div className="rounded-lg border border-surface-border bg-surface-2/60 p-3 text-center">
          <span className="block font-mono text-lg font-bold text-emerald-400">IEC 62443</span>
          <span className="font-mono text-[10px] text-ink-3 uppercase">Purdue Level 3 Air-Gap</span>
        </div>
        <div className="rounded-lg border border-surface-border bg-surface-2/60 p-3 text-center">
          <span className="block font-mono text-lg font-bold text-indigo-400">MULTIMODAL</span>
          <span className="font-mono text-[10px] text-ink-3 uppercase">P&amp;ID CAD + PDF + Graph</span>
        </div>
        <div className="rounded-lg border border-surface-border bg-surface-2/60 p-3 text-center">
          <span className="block font-mono text-lg font-bold text-amber-400">FOUR-EYES</span>
          <span className="font-mono text-[10px] text-ink-3 uppercase">Dual Supervisor Consensus</span>
        </div>
      </div>
    </section>
  );
}
