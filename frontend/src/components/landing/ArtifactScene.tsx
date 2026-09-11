import { IconArchive } from "@/components/ui/Icon";

export function ArtifactScene() {
  return (
    <section className="py-20 px-4 sm:px-8 max-w-6xl mx-auto border-b border-surface-border">
      <div className="text-center max-w-3xl mx-auto mb-12 space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-brand/40 bg-brand/10 px-3 py-0.5 text-xs font-mono text-brand">
          <IconArchive className="h-3.5 w-3.5" />
          <span>CRYPTOGRAPHIC DELIVERABLES</span>
        </div>
        <h2 className="text-2xl sm:text-4xl font-bold text-ink-1">
          Automated Deliverable &amp; Permit Generation
        </h2>
        <p className="text-xs sm:text-sm text-ink-2 leading-relaxed">
          Every agent investigation automatically materializes immutable deliverables:
          statistical CSV charts, work permit authorization certificates, and full Section 17 audit packages stamped with local SHA256 hashes.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Deliverable 1: Work Permit Certificate */}
        <div className="rounded-xl border border-surface-border bg-surface-2/60 p-5 space-y-3 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="rounded bg-brand/15 px-2 py-0.5 font-mono text-[9px] font-bold text-brand uppercase">
                PDF CERTIFICATE
              </span>
              <span className="font-mono text-[10px] text-ink-3">84.2 KB</span>
            </div>
            <h4 className="font-mono text-sm font-bold text-ink-1">
              PERMIT_AUTH_P101A.pdf
            </h4>
            <p className="text-xs text-ink-3 leading-relaxed">
              Official one-time work permit with Zara &amp; Rakshita cryptographic signatures, tool parameters, and 60-minute TTL.
            </p>
          </div>
          <div className="pt-3 border-t border-surface-border font-mono text-[10px] text-ink-3 space-y-1">
            <div className="truncate">SHA256: 7f8a91c4d28e...</div>
            <div className="text-emerald-400 font-bold">✓ VERIFIED LOCAL HASH</div>
          </div>
        </div>

        {/* Deliverable 2: Telemetry Trend SVG */}
        <div className="rounded-xl border border-surface-border bg-surface-2/60 p-5 space-y-3 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="rounded bg-cyan-500/15 px-2 py-0.5 font-mono text-[9px] font-bold text-cyan-400 uppercase">
                SVG TELEMETRY
              </span>
              <span className="font-mono text-[10px] text-ink-3">22.4 KB</span>
            </div>
            <h4 className="font-mono text-sm font-bold text-ink-1">
              PT101_PRESSURE_SURGE.svg
            </h4>
            <p className="text-xs text-ink-3 leading-relaxed">
              High-resolution vector time-series showing pressure spike at 02:48:10 IST against MAWP upper threshold line.
            </p>
          </div>
          <div className="pt-3 border-t border-surface-border font-mono text-[10px] text-ink-3 space-y-1">
            <div className="truncate">SHA256: e3b0c44298fc...</div>
            <div className="text-emerald-400 font-bold">✓ VERIFIED LOCAL HASH</div>
          </div>
        </div>

        {/* Deliverable 3: Section 17 RCA Dossier */}
        <div className="rounded-xl border border-surface-border bg-surface-2/60 p-5 space-y-3 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="rounded bg-amber-500/15 px-2 py-0.5 font-mono text-[9px] font-bold text-amber-400 uppercase">
                HTML DOSSIER
              </span>
              <span className="font-mono text-[10px] text-ink-3">146.0 KB</span>
            </div>
            <h4 className="font-mono text-sm font-bold text-ink-1">
              RCA_SECTION17_DOSSIER.html
            </h4>
            <p className="text-xs text-ink-3 leading-relaxed">
              Complete multi-page legal investigation report including P&amp;ID annotations, sensor telemetry, and corrective actions.
            </p>
          </div>
          <div className="pt-3 border-t border-surface-border font-mono text-[10px] text-ink-3 space-y-1">
            <div className="truncate">SHA256: a8b39c719e0f...</div>
            <div className="text-emerald-400 font-bold">✓ VERIFIED LOCAL HASH</div>
          </div>
        </div>
      </div>
    </section>
  );
}
