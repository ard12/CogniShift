import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";

interface LandingHeaderProps {
  onScrollTo: (sectionId: string) => void;
}

export function LandingHeader({ onScrollTo }: LandingHeaderProps) {
  return (
    <header className="sticky top-0 z-50 flex h-16 w-full items-center justify-between border-b border-surface-border bg-surface-1/90 backdrop-blur-md px-4 sm:px-8">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <span className="text-xl text-brand" aria-hidden="true">
          ⬡
        </span>
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-bold tracking-widest text-ink-1">
              COGNISHIFT
            </span>
            <span className="rounded border border-surface-border bg-surface-3 px-1.5 py-0.2 font-mono text-[9px] font-medium text-brand">
              SIH26117
            </span>
          </div>
          <span className="font-mono text-[10px] text-ink-3">
            Sovereign Industrial AI Workbench
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="hidden lg:flex items-center gap-6 text-xs font-mono text-ink-2">
        <button
          type="button"
          onClick={() => onScrollTo("sovereignty")}
          className="hover:text-brand transition-colors cursor-pointer"
        >
          SOVEREIGNTY
        </button>
        <button
          type="button"
          onClick={() => onScrollTo("hybrid-rag")}
          className="hover:text-brand transition-colors cursor-pointer"
        >
          MULTIMODAL RAG
        </button>
        <button
          type="button"
          onClick={() => onScrollTo("pid-vision")}
          className="hover:text-brand transition-colors cursor-pointer"
        >
          P&ID VISION
        </button>
        <button
          type="button"
          onClick={() => onScrollTo("rca-protocol")}
          className="hover:text-brand transition-colors cursor-pointer"
        >
          SECTION 17 RCA
        </button>
        <button
          type="button"
          onClick={() => onScrollTo("governance")}
          className="hover:text-brand transition-colors cursor-pointer"
        >
          FOUR-EYES GOV
        </button>
        <button
          type="button"
          onClick={() => onScrollTo("topology")}
          className="hover:text-brand transition-colors cursor-pointer"
        >
          AIR-GAP TOPOLOGY
        </button>
      </nav>

      {/* Action / Launch */}
      <div className="flex items-center gap-3">
        <div className="hidden sm:flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-mono text-emerald-400">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>ZERO CLOUD EGRESS</span>
        </div>

        <Link to="/app/operator">
          <Button
            size="sm"
            variant="primary"
            className="font-mono text-xs font-semibold px-3 py-1.5"
          >
            Launch Workbench →
          </Button>
        </Link>
      </div>
    </header>
  );
}
