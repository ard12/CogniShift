import { IconCpu } from "@/components/ui/Icon";

export function LocalExecutionScene() {
  return (
    <section id="topology" className="py-20 px-4 sm:px-8 max-w-6xl mx-auto border-b border-surface-border">
      <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-brand/40 bg-brand/10 px-3 py-0.5 text-xs font-mono text-brand">
          <IconCpu className="h-3.5 w-3.5" />
          <span>ON-PREMISE HARDWARE TOPOLOGY</span>
        </div>
        <h2 className="text-2xl sm:text-4xl font-bold text-ink-1">
          Engineered for Consumer &amp; Industrial Edge Silicon
        </h2>
        <p className="text-xs sm:text-sm text-ink-2 leading-relaxed">
          Tested and optimized on entry-level edge hardware (NVIDIA RTX 3050 4GB / 6GB VRAM &amp; Intel/AMD 8-core CPUs).
          Delivers industrial-grade inference without requiring multimillion-dollar data center clusters.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-surface-border bg-surface-2/60 p-5 space-y-2">
          <span className="font-mono text-[10px] text-brand font-bold uppercase tracking-wider block">
            EDGE GPU REASONING
          </span>
          <p className="text-lg font-bold font-mono text-ink-1">NVIDIA RTX 3050</p>
          <div className="space-y-1 font-mono text-xs text-ink-3">
            <div>Quantization: <span className="text-ink-1">Q4_K_M (Ollama)</span></div>
            <div>VRAM Allocated: <span className="text-brand font-bold">4.2 GB / 6.0 GB</span></div>
            <div>Inference Speed: <span className="text-emerald-400">~24 tok/sec</span></div>
          </div>
        </div>

        <div className="rounded-xl border border-surface-border bg-surface-2/60 p-5 space-y-2">
          <span className="font-mono text-[10px] text-cyan-400 font-bold uppercase tracking-wider block">
            VECTOR SUBSTRATE
          </span>
          <p className="text-lg font-bold font-mono text-ink-1">ChromaDB + ONNX</p>
          <div className="space-y-1 font-mono text-xs text-ink-3">
            <div>Vector Engine: <span className="text-ink-1">HNSW Cosine Index</span></div>
            <div>Embed Latency: <span className="text-cyan-400 font-bold">14ms (FastEmbed)</span></div>
            <div>Storage: <span className="text-ink-1">Local SSD Flat Files</span></div>
          </div>
        </div>

        <div className="rounded-xl border border-surface-border bg-surface-2/60 p-5 space-y-2">
          <span className="font-mono text-[10px] text-emerald-400 font-bold uppercase tracking-wider block">
            CONCURRENT LEDGER
          </span>
          <p className="text-lg font-bold font-mono text-ink-1">SQLite 3 WAL</p>
          <div className="space-y-1 font-mono text-xs text-ink-3">
            <div>Concurrency: <span className="text-ink-1">WAL Mode + Busy Timeout</span></div>
            <div>Foreign Keys: <span className="text-emerald-400 font-bold">PRAGMA ON</span></div>
            <div>Lock Contention: <span className="text-ink-1">Zero During LLM Stream</span></div>
          </div>
        </div>

        <div className="rounded-xl border border-surface-border bg-surface-2/60 p-5 space-y-2">
          <span className="font-mono text-[10px] text-amber-400 font-bold uppercase tracking-wider block">
            EXECUTION SANDBOX
          </span>
          <p className="text-lg font-bold font-mono text-ink-1">Docker Isolated</p>
          <div className="space-y-1 font-mono text-xs text-ink-3">
            <div>Network Mode: <span className="text-amber-300 font-bold">--net=none (Air-Gap)</span></div>
            <div>Memory Limit: <span className="text-ink-1">512 MB Max</span></div>
            <div>Execution Timeout: <span className="text-ink-1">30s Fail-Closed</span></div>
          </div>
        </div>
      </div>
    </section>
  );
}
