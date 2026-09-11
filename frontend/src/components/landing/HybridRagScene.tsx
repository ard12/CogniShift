import { useState } from "react";
import { IconBook, IconCheck } from "@/components/ui/Icon";

type ChannelType = "bundle" | "fastembed" | "colmodern" | "topology";

export function HybridRagScene() {
  const [activeTab, setActiveTab] = useState<ChannelType>("bundle");

  return (
    <section id="hybrid-rag" className="py-20 px-4 sm:px-8 max-w-6xl mx-auto border-b border-surface-border">
      <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-brand/40 bg-brand/10 px-3 py-0.5 text-xs font-mono text-brand">
          <IconBook className="h-3.5 w-3.5" />
          <span>TRI-MODAL EVIDENCE SYNTHESIS</span>
        </div>
        <h2 className="text-2xl sm:text-4xl font-bold text-ink-1">
          Hybrid Multimodal Retrieval-Augmented Generation
        </h2>
        <p className="text-xs sm:text-sm text-ink-2 leading-relaxed">
          Standard text-only RAG fails on industrial engineering documents filled with complex P&amp;ID blueprints, sensor wiring schematics, and equipment hierarchies.
          CogniShift fuses three independent physical evidence channels.
        </p>
      </div>

      {/* Channel Selector Tabs */}
      <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
        <button
          type="button"
          onClick={() => setActiveTab("bundle")}
          className={`rounded-lg px-4 py-2 text-xs font-mono font-semibold transition cursor-pointer border ${
            activeTab === "bundle"
              ? "bg-brand text-black border-brand shadow-sm"
              : "bg-surface-2 text-ink-2 border-surface-border hover:bg-surface-3"
          }`}
        >
          Fused Evidence Bundle (Verified)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("fastembed")}
          className={`rounded-lg px-4 py-2 text-xs font-mono font-semibold transition cursor-pointer border ${
            activeTab === "fastembed"
              ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40"
              : "bg-surface-2 text-ink-2 border-surface-border hover:bg-surface-3"
          }`}
        >
          Channel 1: FastEmbed Dense Text
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("colmodern")}
          className={`rounded-lg px-4 py-2 text-xs font-mono font-semibold transition cursor-pointer border ${
            activeTab === "colmodern"
              ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/40"
              : "bg-surface-2 text-ink-2 border-surface-border hover:bg-surface-3"
          }`}
        >
          Channel 2: ColModernVBERT Visual
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("topology")}
          className={`rounded-lg px-4 py-2 text-xs font-mono font-semibold transition cursor-pointer border ${
            activeTab === "topology"
              ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
              : "bg-surface-2 text-ink-2 border-surface-border hover:bg-surface-3"
          }`}
        >
          Channel 3: Asset Graph &amp; Topology
        </button>
      </div>

      {/* Interactive Display Area */}
      <div className="rounded-xl border border-surface-border bg-surface-2/60 p-6 shadow-xl">
        {activeTab === "bundle" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-surface-border pb-3">
              <span className="font-mono text-xs font-bold text-ink-1 uppercase tracking-wider">
                Authoritative Evidence Bundle [E1, E2, E3]
              </span>
              <span className="font-mono text-[10px] text-emerald-400 font-semibold">
                STRICT DISTANCE FILTERING (≤ 0.78) ENFORCED
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="evidence-channel-fastembed rounded-r-lg border border-surface-border bg-surface-1 p-3.5 space-y-1.5">
                <span className="font-mono text-[10px] text-cyan-400 font-bold uppercase block">
                  [E1] Dense Text Retrieval
                </span>
                <p className="text-xs font-semibold text-ink-1">O&amp;M SOP Manual (p. 42)</p>
                <p className="text-[11px] text-ink-3 leading-relaxed">
                  "Centrifugal pump P-101A maximum allowable discharge pressure is 450 PSI. Relief valve SV-402 must open at 460 PSI."
                </p>
                <span className="font-mono text-[9px] text-cyan-400 font-bold">Cosine Dist: 0.18</span>
              </div>

              <div className="evidence-channel-colmodern rounded-r-lg border border-surface-border bg-surface-1 p-3.5 space-y-1.5">
                <span className="font-mono text-[10px] text-indigo-400 font-bold uppercase block">
                  [E2] Visual P&amp;ID Reasoning
                </span>
                <p className="text-xs font-semibold text-ink-1">DWG P-ID-04-B (Sheet 2)</p>
                <p className="text-[11px] text-ink-3 leading-relaxed">
                  ColModernVBERT multi-vector patch matches valve FV-302 tag bubble coordinates [ymin: 412, xmin: 120, ymax: 480, xmax: 210].
                </p>
                <span className="font-mono text-[9px] text-indigo-400 font-bold">Late Interaction: 0.892</span>
              </div>

              <div className="evidence-channel-topology rounded-r-lg border border-surface-border bg-surface-1 p-3.5 space-y-1.5">
                <span className="font-mono text-[10px] text-emerald-400 font-bold uppercase block">
                  [E3] Topology Relationship
                </span>
                <p className="text-xs font-semibold text-ink-1">Refinery Asset Graph</p>
                <p className="text-[11px] text-ink-3 leading-relaxed">
                  Sensor PT-101 is mounted on the discharge spool of Pump P-101A upstream of Reactor R-301 isolation block valve.
                </p>
                <span className="font-mono text-[9px] text-emerald-400 font-bold">Graph Hops: 1</span>
              </div>
            </div>

            <div className="rounded border border-emerald-500/30 bg-emerald-500/10 p-3 flex items-center justify-between text-xs font-mono text-emerald-300">
              <div className="flex items-center gap-2">
                <IconCheck className="h-4 w-4 text-emerald-400" />
                <span>Evidence Bundle Grounding Validated: Zero Distractor Hallucinations Allowed</span>
              </div>
              <span className="font-bold">CONFIDENCE: 98.2%</span>
            </div>
          </div>
        )}

        {activeTab === "fastembed" && (
          <div className="space-y-3 font-mono text-xs">
            <div className="border-b border-surface-border pb-2 flex items-center justify-between">
              <span className="text-cyan-400 font-bold">FastEmbed Engine (bge-small-en-v1.5)</span>
              <span className="text-ink-3">Latency: 14ms on Local CPU</span>
            </div>
            <p className="text-ink-2 font-sans text-xs">
              FastEmbed runs in-process with zero remote network calls. Text documents are chunked with recursive boundary preservation (headers, table cells, step procedures).
            </p>
            <div className="rounded border border-surface-border bg-surface-1 p-3 text-[11px] text-ink-2 space-y-1">
              <div>Query: "normal operating pressure for sensor PT-101"</div>
              <div>Top Chunks: 3 matched</div>
              <div>Max Distance Threshold Filter: 0.78 (Out-of-domain chunks suppressed)</div>
            </div>
          </div>
        )}

        {activeTab === "colmodern" && (
          <div className="space-y-3 font-mono text-xs">
            <div className="border-b border-surface-border pb-2 flex items-center justify-between">
              <span className="text-indigo-400 font-bold">ColModernVBERT / ColPali Multi-Vector Visual</span>
              <span className="text-ink-3">Patch Size: 32x32 Tokens</span>
            </div>
            <p className="text-ink-2 font-sans text-xs">
              Directly indexes scanned engineering drawings, equipment nameplates, and P&amp;ID blueprints without lossy OCR preprocessing.
              Queries interact with patch tokens via MaxSim late-interaction.
            </p>
            <div className="rounded border border-surface-border bg-surface-1 p-3 text-[11px] text-ink-2 space-y-1">
              <div>Target: "bypass isolation valve FV-302"</div>
              <div>Matched Patch Matrix: 1024 visual tokens against CAD sheet P-ID-04-B</div>
              <div>Score: 0.892 (High spatial correlation)</div>
            </div>
          </div>
        )}

        {activeTab === "topology" && (
          <div className="space-y-3 font-mono text-xs">
            <div className="border-b border-surface-border pb-2 flex items-center justify-between">
              <span className="text-emerald-400 font-bold">Knowledge Graph &amp; Industrial Asset Topology</span>
              <span className="text-ink-3">Graph Nodes: 1,420 | Edges: 3,840</span>
            </div>
            <p className="text-ink-2 font-sans text-xs">
              Maintains true physical hierarchy: Substation &gt; Motor Breaker &gt; Centrifugal Pump &gt; Discharge Line &gt; Reactor.
              Prevents the AI from diagnosing a valve failure on an unrelated process unit.
            </p>
            <div className="rounded border border-surface-border bg-surface-1 p-3 text-[11px] text-ink-2 space-y-1">
              <div>Path: PT-101 (Sensor) --[monitors]--&gt; P-101A (Pump) --[feeds]--&gt; R-301 (Reactor)</div>
              <div>Interlocks: SV-402 (Pressure Safety Valve), FV-302 (Flow Control Valve)</div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
